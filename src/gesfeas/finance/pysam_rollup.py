"""
Shared PySAM financial rollup (G10).

Both the PV-only and PV+Storage engines value energy with ``PySAM.Utilityrate5``
and roll it up into NPV / payback / LCOE with ``PySAM.Cashloan`` — the SAME
compute engine used by the SAM desktop GUI. This module is the single place
where that chain is wired, so the two engines stay consistent.

Design notes
------------
* Utilityrate5 and Cashloan share one ssc data table (``Cashloan.from_existing``)
  so the utility-bill outputs (``utility_bill_w_sys`` etc.) flow automatically
  into Cashloan.
* ``gen_meter`` is the system output as seen by the meter (for PV+Storage this is
  PV minus battery charging plus battery discharge). ``load`` is the site's REAL
  load — Utilityrate5 derives the "without-system" baseline bill from it, so the
  raw load (not a net series) MUST be passed for savings to be correct.
* ``lcoe_gen`` is the real PV production used only as the LCOE energy denominator.
* Netting regime maps to ``ur_metering_option``: hourly netting -> net billing
  (per-timestep), monthly netting / mahsuplaşma -> net metering (monthly rollover).
* No silent fallback: any PySAM execution failure raises ``RuntimeError``.
"""

import math
from typing import List, NamedTuple, Optional, Tuple

import PySAM.Cashloan as Cashloan
import PySAM.Utilityrate5 as Utilityrate5

from .models import TariffConfig

# Netting regime -> Utilityrate5 metering option.
#   2 = Net Billing        (per-timestep netting  -> "hourly"  / saatlik mahsup)
#   0 = Net Energy Metering (monthly rollover      -> "monthly" / aylık mahsup)
NETTING_TO_METERING = {"hourly": 2, "monthly": 0}

_HOURS = 8760


class RollupResult(NamedTuple):
    annual_savings: float
    npv: float
    simple_payback: float
    discounted_payback: float
    lcoe: float


def _clean_payback(value: Optional[float], lifetime: int) -> float:
    """PySAM returns NaN (or <=0) when payback never occurs -> cap at lifetime."""
    if value is None or (isinstance(value, float) and math.isnan(value)) or value <= 0:
        return float(lifetime)
    return float(value)


def run_cashloan_rollup(
    *,
    gen_meter: List[float],
    load: List[float],
    lcoe_gen: List[float],
    total_capex: float,
    system_kw: float,
    opex_per_kw_year: float,
    tariff: TariffConfig,
    degradation_pct: float,
    netting_mode: str = "hourly",
    replacement: Optional[Tuple[int, float]] = None,
) -> RollupResult:
    """Run the Utilityrate5 -> Cashloan chain and return financial metrics.

    Parameters
    ----------
    gen_meter : 8760 hourly system output seen by the meter (kWh).
    load : 8760 hourly REAL site load (kWh).
    lcoe_gen : 8760 hourly real PV production (kWh) — LCOE energy denominator.
    total_capex : total installed cost (USD).
    system_kw : system capacity (kW), used for O&M and reporting.
    opex_per_kw_year : fixed O&M (USD/kW-year), escalated by inflation.
    tariff : TariffConfig (discount/inflation/lifetime/debt/loan, buy/sell prices).
    degradation_pct : annual production degradation (percent/year).
    netting_mode : "hourly" or "monthly".
    replacement : optional (year, amount_usd) one-off cost (e.g. battery swap),
        placed as a fixed O&M expense in that year (discounted by Cashloan).
    """
    if netting_mode not in NETTING_TO_METERING:
        raise ValueError(
            f"Unknown netting_mode {netting_mode!r}; expected one of "
            f"{sorted(NETTING_TO_METERING)}"
        )
    for name, series in (("gen_meter", gen_meter), ("load", load), ("lcoe_gen", lcoe_gen)):
        if len(series) != _HOURS:
            raise ValueError(f"{name} must have {_HOURS} hourly values, got {len(series)}")

    buy = tariff.buy_price_kwh
    sell = tariff.sell_price_kwh
    lifetime = tariff.lifetime

    # ---- Utilityrate5: value the energy ----
    ur = Utilityrate5.new()
    cl = Cashloan.from_existing(ur)  # shared ssc data table

    ur.Lifetime.analysis_period = lifetime
    ur.Lifetime.inflation_rate = tariff.inflation_rate
    ur.Lifetime.system_use_lifetime_output = 0
    ur.SystemOutput.gen = gen_meter
    ur.SystemOutput.degradation = [degradation_pct]
    ur.Load.load = load

    er = ur.ElectricityRates
    er.en_electricity_rates = 1
    er.ur_metering_option = NETTING_TO_METERING[netting_mode]
    er.ur_monthly_fixed_charge = 0.0
    # Single flat energy-charge period (buy/sell) for all months/hours.
    er.ur_ec_sched_weekday = [[1] * 24] * 12
    er.ur_ec_sched_weekend = [[1] * 24] * 12
    er.ur_ec_tou_mat = [[1, 1, 9.9e37, 0, buy, sell]]
    er.ur_nm_yearend_sell_rate = sell

    try:
        ur.execute(0)
    except Exception as exc:  # noqa: BLE001 - re-raise with context, never fall back
        raise RuntimeError(f"Utilityrate5 execution failed: {exc}") from exc

    annual_savings = float(ur.Outputs.savings_year1)

    # ---- Cashloan: CAPEX, debt, O&M, discounting -> NPV / payback / LCOE ----
    fp = cl.FinancialParameters
    fp.analysis_period = lifetime
    fp.debt_fraction = tariff.debt_fraction
    fp.loan_term = tariff.loan_term
    fp.loan_rate = tariff.loan_rate
    fp.inflation_rate = tariff.inflation_rate
    # Cashloan wants the REAL discount rate; derive it from the nominal rate.
    nominal = tariff.discount_rate / 100.0
    infl = tariff.inflation_rate / 100.0
    fp.real_discount_rate = ((1 + nominal) / (1 + infl) - 1) * 100.0
    fp.federal_tax_rate = [0.0]
    fp.state_tax_rate = [0.0]
    fp.property_tax_rate = 0.0
    fp.insurance_rate = 0.0
    fp.salvage_percentage = 0.0
    fp.system_capacity = system_kw
    fp.prop_tax_cost_assessed_percent = 0.0
    fp.prop_tax_assessed_decline = 0.0
    fp.market = 1  # commercial
    fp.mortgage = 0

    sc = cl.SystemCosts
    sc.total_installed_cost = total_capex
    sc.om_capacity = [opex_per_kw_year]
    sc.om_capacity_escal = 0.0
    if replacement is not None:
        year, amount = replacement
        fixed = [0.0] * lifetime
        if 1 <= year <= lifetime:
            fixed[year - 1] = amount
        sc.om_fixed = fixed
        sc.om_fixed_escal = 0.0

    # LCOE energy denominator = real PV production (not the metered net series).
    cl.SystemOutput.gen = lcoe_gen
    cl.SystemOutput.degradation = [degradation_pct]
    cl.Lifetime.system_use_lifetime_output = 0

    try:
        cl.execute(0)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Cashloan execution failed: {exc}") from exc

    out = cl.Outputs
    return RollupResult(
        annual_savings=annual_savings,
        npv=float(out.npv),
        simple_payback=_clean_payback(out.payback, lifetime),
        discounted_payback=_clean_payback(out.discounted_payback, lifetime),
        lcoe=float(out.lcoe_nom) / 100.0,  # cents/kWh -> USD/kWh
    )
