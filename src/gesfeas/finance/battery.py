"""
Battery dispatch and PV+Storage finance engine (G4).

Implements behind-the-meter self-consumption optimisation with battery storage.
Generates hourly load profiles from monthly consumption using shift patterns.
"""

import datetime
from typing import List, NamedTuple

import PySAM.Lcoefcr as lcoe

from gesfeas.input.models import ShiftPattern
from .models import BatteryConfig, BatteryFinanceInput, BatteryFinanceResult, TariffConfig


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REFERENCE_YEAR = 2026  # Non-leap year → 365 days → 8 760 hours
PV_DEGRADATION_RATE = 0.005  # 0.5 %/year (matches G3 engine.py)

# Hourly load-weight profiles per shift pattern (24 values for hours 0–23).
# Higher weight ⇒ higher load intensity in that hour.
_SHIFT_WEIGHTS = {
    ShiftPattern.SINGLE: [
        # 00–07: low base load (standby / security / lighting)
        0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.40,
        # 08–15: full operation
        1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00,
        # 16–23: ramp-down then base load
        1.00, 0.60, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15,
    ],
    ShiftPattern.DOUBLE: [
        0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.80, 1.00,
        1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00,
        1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 0.80, 0.15,
    ],
    ShiftPattern.TRIPLE: [
        0.85, 0.85, 0.85, 0.85, 0.85, 0.85, 0.90, 1.00,
        1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00,
        1.00, 1.00, 1.00, 1.00, 1.00, 0.95, 0.90, 0.85,
    ],
    # WEEKEND_CLOSED uses same weekday profile as SINGLE;
    # weekend hours are replaced with _WEEKEND_WEIGHT (see below).
    ShiftPattern.WEEKEND_CLOSED: [
        0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15, 0.40,
        1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00, 1.00,
        1.00, 0.60, 0.15, 0.15, 0.15, 0.15, 0.15, 0.15,
    ],
}

_WEEKEND_WEIGHT = 0.05  # Minimal load on weekends for WEEKEND_CLOSED


# ---------------------------------------------------------------------------
# Load-profile generation
# ---------------------------------------------------------------------------

def generate_hourly_load_profile(
    monthly_consumption: List[float],
    shift_pattern: ShiftPattern,
) -> List[float]:
    """Generate an 8 760-hour load profile from 12 monthly totals + shift pattern.

    Each month's consumption is distributed across its hours using the
    shift-pattern weights, normalised so the month's hours sum to the
    monthly total exactly.

    Uses ``REFERENCE_YEAR`` (2026, non-leap) so the profile always has
    exactly 8 760 entries.
    """
    if len(monthly_consumption) != 12:
        raise ValueError(f"Expected 12 monthly values, got {len(monthly_consumption)}")

    weights = _SHIFT_WEIGHTS[shift_pattern]
    is_weekend_closed = shift_pattern == ShiftPattern.WEEKEND_CLOSED

    hourly_load: List[float] = []

    for month_idx in range(12):
        month = month_idx + 1
        # Days in this month
        if month == 12:
            next_month_start = datetime.date(REFERENCE_YEAR + 1, 1, 1)
        else:
            next_month_start = datetime.date(REFERENCE_YEAR, month + 1, 1)
        days_in_month = (next_month_start - datetime.date(REFERENCE_YEAR, month, 1)).days

        # Build raw weight list for every hour of this month
        raw: List[float] = []
        for day in range(1, days_in_month + 1):
            dt = datetime.date(REFERENCE_YEAR, month, day)
            is_weekend = dt.weekday() >= 5  # Saturday = 5, Sunday = 6
            for hour in range(24):
                if is_weekend and is_weekend_closed:
                    raw.append(_WEEKEND_WEIGHT)
                else:
                    raw.append(weights[hour])

        # Scale so hours sum to the monthly total
        total_weight = sum(raw)
        monthly_total = monthly_consumption[month_idx]
        if total_weight > 0 and monthly_total > 0:
            factor = monthly_total / total_weight
            hourly_load.extend(w * factor for w in raw)
        else:
            hourly_load.extend(0.0 for _ in raw)

    if len(hourly_load) != 8760:
        raise RuntimeError(
            f"Generated profile has {len(hourly_load)} hours, expected 8760"
        )
    return hourly_load


# ---------------------------------------------------------------------------
# Battery dispatch simulation
# ---------------------------------------------------------------------------

class DispatchResult(NamedTuple):
    """Aggregated results from one year of hourly battery dispatch."""
    year1_savings: float
    pv_direct_savings: float
    battery_incremental_savings: float
    self_consumption_ratio: float
    grid_export_ratio: float
    battery_cycles_year1: float


def _run_dispatch(
    hourly_production: List[float],
    hourly_load: List[float],
    battery: BatteryConfig,
    tariff: TariffConfig,
) -> DispatchResult:
    """Simulate one year of hourly battery dispatch.

    Strategy — behind-the-meter self-consumption optimisation:

    1. PV serves load directly (self-consumption).
    2. Excess PV charges the battery (power / capacity limited).
    3. Remaining excess is exported to the grid.
    4. When load > PV, battery discharges to cover the deficit.
    5. Remaining deficit is met by grid import.
    """
    capacity = battery.battery_capacity_kwh
    max_power = battery.battery_power_kw
    eff = battery.round_trip_efficiency
    # Split round-trip efficiency symmetrically: η_rt = η_chg × η_dis
    charge_eff = eff ** 0.5
    discharge_eff = eff ** 0.5

    soc = 0.0  # State of charge (kWh)

    pv_to_load = 0.0
    pv_to_battery = 0.0
    pv_to_grid = 0.0
    battery_to_load = 0.0
    total_discharge_energy = 0.0  # Energy removed from battery (pre-loss)

    for h in range(8760):
        pv = hourly_production[h]
        load = hourly_load[h]

        # 1. Direct self-consumption
        direct = min(pv, load)
        pv_to_load += direct
        remaining_pv = pv - direct
        remaining_load = load - direct

        # 2. Charge battery from excess PV
        if remaining_pv > 0 and soc < capacity:
            available_capacity = (capacity - soc) / charge_eff
            charge = min(remaining_pv, max_power, available_capacity)
            soc += charge * charge_eff
            soc = min(soc, capacity)  # clamp
            remaining_pv -= charge
            pv_to_battery += charge

        # 3. Discharge battery to cover unmet load
        if remaining_load > 0 and soc > 0:
            available_discharge = soc * discharge_eff
            discharge = min(remaining_load, max_power, available_discharge)
            energy_removed = discharge / discharge_eff
            soc -= energy_removed
            soc = max(soc, 0.0)  # clamp
            remaining_load -= discharge
            battery_to_load += discharge
            total_discharge_energy += energy_removed

        # 4. Export remaining PV / import remaining load
        pv_to_grid += remaining_pv

    total_pv = sum(hourly_production)

    # ---- Physical metrics ----
    if total_pv > 0:
        self_consumption_ratio = (pv_to_load + pv_to_battery) / total_pv
        grid_export_ratio = pv_to_grid / total_pv
    else:
        self_consumption_ratio = 0.0
        grid_export_ratio = 1.0

    battery_cycles = total_discharge_energy / capacity if capacity > 0 else 0.0

    # ---- Financial metrics (year 1) ----
    buy = tariff.buy_price_kwh
    sell = tariff.sell_price_kwh

    year1_savings = (pv_to_load + battery_to_load) * buy + pv_to_grid * sell

    # PV-only component (savings if no battery were present)
    pv_direct_savings = pv_to_load * buy + (pv_to_battery + pv_to_grid) * sell
    battery_incremental = year1_savings - pv_direct_savings

    return DispatchResult(
        year1_savings=year1_savings,
        pv_direct_savings=pv_direct_savings,
        battery_incremental_savings=battery_incremental,
        self_consumption_ratio=self_consumption_ratio,
        grid_export_ratio=grid_export_ratio,
        battery_cycles_year1=battery_cycles,
    )


# ---------------------------------------------------------------------------
# PV + Storage finance engine
# ---------------------------------------------------------------------------

def run_pv_storage_finance(inputs: BatteryFinanceInput) -> BatteryFinanceResult:
    """Run the PV+Storage techno-economic model.

    1. Generate hourly load profile from monthly consumption + shift pattern.
    2. Simulate battery dispatch for year 1.
    3. Compute lifetime cash flows (NPV, LCOE, payback).

    The existing PV-only path (``run_pv_finance``) is not touched.
    """
    t = inputs.tariff
    bat = inputs.battery
    shift = ShiftPattern(inputs.shift_pattern)

    # ---- Hourly load profile ----
    hourly_load = generate_hourly_load_profile(inputs.monthly_consumption, shift)

    # ---- Battery dispatch (year 1) ----
    dispatch = _run_dispatch(inputs.production_series, hourly_load, bat, t)

    # ---- CAPEX ----
    pv_capex = inputs.system_size_kw * t.capex_per_kw
    battery_capex = bat.battery_capacity_kwh * bat.battery_capex_per_kwh
    total_capex = pv_capex + battery_capex

    # ---- LCOE (PySAM Lcoefcr) ----
    # LCOE is computed on PV generation; battery shifts timing, doesn't generate.
    year1_gen = sum(inputs.production_series)

    m = lcoe.new()
    m.SimpleLCOE.capital_cost = total_capex
    m.SimpleLCOE.fixed_operating_cost = inputs.system_size_kw * t.opex_per_kw_year
    m.SimpleLCOE.variable_operating_cost = 0.0

    rate = t.discount_rate / 100.0
    if rate > 0:
        fcr = rate / (1 - (1 + rate) ** -t.lifetime)
    else:
        fcr = 1.0 / t.lifetime
    m.SimpleLCOE.fixed_charge_rate = fcr
    m.SimpleLCOE.annual_energy = year1_gen
    m.execute()
    lcoe_val = m.Outputs.lcoe_fcr

    # ---- Cash flow, NPV, payback ----
    inflation = t.inflation_rate / 100.0
    discount = t.discount_rate / 100.0
    pv_deg = PV_DEGRADATION_RATE
    bat_deg = bat.battery_degradation_rate
    replacement_year = bat.battery_replacement_year

    pv_direct_sav = dispatch.pv_direct_savings
    bat_incr_sav = dispatch.battery_incremental_savings

    npv = float(-total_capex)
    cumulative_cash = float(-total_capex)
    cumulative_disc = float(-total_capex)
    simple_payback = -1.0
    discounted_payback = -1.0

    for year in range(1, t.lifetime + 1):
        # PV production degradation
        pv_factor = (1 - pv_deg) ** (year - 1)

        # Battery capacity degradation (resets after replacement)
        if year > replacement_year:
            years_since = year - replacement_year
            bat_factor = max(0.0, (1 - bat_deg) ** (years_since - 1))
        else:
            bat_factor = max(0.0, (1 - bat_deg) ** (year - 1))

        infl_factor = (1 + inflation) ** (year - 1)

        current_savings = (
            pv_direct_sav * pv_factor
            + bat_incr_sav * pv_factor * bat_factor
        ) * infl_factor
        current_opex = (inputs.system_size_kw * t.opex_per_kw_year) * infl_factor

        net_cf = current_savings - current_opex

        # Battery replacement cost
        if year == replacement_year:
            replacement_cost = (
                bat.battery_capacity_kwh * bat.battery_replacement_cost_per_kwh
            )
            net_cf -= replacement_cost

        disc_cf = net_cf / ((1 + discount) ** year)
        npv += disc_cf

        # Payback tracking
        if cumulative_cash < 0 and cumulative_cash + net_cf >= 0 and simple_payback < 0:
            simple_payback = (year - 1) + abs(cumulative_cash) / net_cf
        cumulative_cash += net_cf

        if cumulative_disc < 0 and cumulative_disc + disc_cf >= 0 and discounted_payback < 0:
            discounted_payback = (year - 1) + abs(cumulative_disc) / disc_cf
        cumulative_disc += disc_cf

    return BatteryFinanceResult(
        capex=total_capex,
        annual_savings=dispatch.year1_savings,
        npv=npv,
        lcoe=lcoe_val,
        simple_payback=simple_payback if simple_payback > 0 else float(t.lifetime),
        discounted_payback=discounted_payback if discounted_payback > 0 else float(t.lifetime),
        self_consumption_ratio=dispatch.self_consumption_ratio,
        grid_export_ratio=dispatch.grid_export_ratio,
        battery_cycles_year1=dispatch.battery_cycles_year1,
    )
