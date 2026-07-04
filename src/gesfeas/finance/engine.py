"""
PV-only techno-economic engine (G3, migrated to PySAM in G10).

Energy is valued by PySAM.Utilityrate5 and rolled up into NPV / payback / LCOE by
PySAM.Cashloan (see finance/pysam_rollup.py). No hand-rolled cash-flow math.
"""

from .models import FinanceInput, FinanceResult
from .pysam_rollup import run_cashloan_rollup


def run_pv_finance(inputs: FinanceInput, netting_mode: str = "hourly") -> FinanceResult:
    """
    Run a PV-ONLY techno-economic model via NREL-PySAM (Utilityrate5 + Cashloan).

    Parameters
    ----------
    inputs : FinanceInput with system_size_kw, 8760 production_series, optional
        consumption_series, and a TariffConfig.
    netting_mode : "hourly" (net billing, per-timestep) or "monthly" (net metering,
        monthly rollover / aylık mahsuplaşma). Defaults to "hourly", preserving the
        pre-G10 behaviour where self-consumption offsets the buy price at each hour.
    """
    t = inputs.tariff
    sys_kw = inputs.system_size_kw
    gen = inputs.production_series
    load = inputs.consumption_series if inputs.consumption_series else [0.0] * len(gen)

    capex = sys_kw * t.capex_per_kw

    result = run_cashloan_rollup(
        gen_meter=gen,
        load=load,
        lcoe_gen=gen,
        total_capex=capex,
        system_kw=sys_kw,
        opex_per_kw_year=t.opex_per_kw_year,
        tariff=t,
        degradation_pct=t.pv_degradation_rate,
        netting_mode=netting_mode,
    )

    return FinanceResult(
        capex=capex,
        annual_savings=result.annual_savings,
        npv=result.npv,
        lcoe=result.lcoe,
        simple_payback=result.simple_payback,
        discounted_payback=result.discounted_payback,
    )
