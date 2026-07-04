import pytest
import json
import os
from gesfeas.finance.models import TariffConfig, FinanceInput, FinanceResult
from gesfeas.finance.engine import run_pv_finance

@pytest.fixture
def base_tariff():
    return TariffConfig(
        capex_per_kw=600.0,
        opex_per_kw_year=10.0,
        inflation_rate=2.5,
        discount_rate=8.0,
        lifetime=25,
        loan_term=10,
        loan_rate=5.0,
        debt_fraction=70.0,
        buy_price_kwh=0.12,
        sell_price_kwh=0.08
    )

@pytest.fixture
def base_input(base_tariff):
    # 100 kW system, 1500 kWh/kW/yr = 150,000 kWh/yr
    # 8760 hours of gen and load
    # Simplify: 17.123 kWh per hour gen
    gen = [150000.0 / 8760] * 8760
    # Load: 100000 kWh/yr => 11.415 kWh per hour load
    load = [100000.0 / 8760] * 8760
    
    return FinanceInput(
        system_size_kw=100.0,
        production_series=gen,
        consumption_series=load,
        tariff=base_tariff
    )

def test_finance_golden_file(base_input):
    """
    Test against a pinned reference snapshot.
    """
    result = run_pv_finance(base_input)
    
    golden_path = os.path.join(os.path.dirname(__file__), "golden", "g3_reference.json")

    # Golden must exist and match — no self-healing auto-write (drift must fail loudly).
    assert os.path.exists(golden_path), (
        "g3_reference.json is missing. Regenerate it deliberately via "
        "scratch/regen_goldens_g10.py and review the change."
    )

    with open(golden_path, "r") as f:
        golden_data = json.load(f)
        
    assert result.capex == pytest.approx(golden_data["capex"], rel=1e-3)
    assert result.annual_savings == pytest.approx(golden_data["annual_savings"], rel=1e-3)
    assert result.npv == pytest.approx(golden_data["npv"], rel=1e-3)
    assert result.lcoe == pytest.approx(golden_data["lcoe"], rel=1e-2)
    assert result.simple_payback == pytest.approx(golden_data["simple_payback"], rel=1e-2)
    assert result.discounted_payback == pytest.approx(golden_data["discounted_payback"], rel=1e-2)

def test_finance_config_driven(base_input):
    """
    Test that changing tariff config changes results (without code change).
    """
    res_base = run_pv_finance(base_input)
    
    # Modify tariff config slightly
    t2 = base_input.tariff.model_copy(update={"capex_per_kw": 800.0, "buy_price_kwh": 0.20})
    input2 = FinanceInput(
        system_size_kw=base_input.system_size_kw,
        production_series=base_input.production_series,
        consumption_series=base_input.consumption_series,
        tariff=t2
    )
    res_mod = run_pv_finance(input2)

    assert res_mod.capex > res_base.capex
    assert res_mod.annual_savings > res_base.annual_savings
    assert res_mod.npv != res_base.npv


def _with_tariff(base_input, **updates):
    """Clone a FinanceInput with a modified tariff (no code change to the engine)."""
    t2 = base_input.tariff.model_copy(update=updates)
    return FinanceInput(
        system_size_kw=base_input.system_size_kw,
        production_series=base_input.production_series,
        consumption_series=base_input.consumption_series,
        tariff=t2,
    )


def test_debt_params_affect_npv(base_input):
    """G10: debt_fraction/loan_rate were previously DEAD — now they must move NPV.

    This test fails against the old hand-rolled (all-equity) engine and passes
    against the PySAM Cashloan engine that actually models the loan.
    """
    base = run_pv_finance(base_input)

    res_cheap_loan = run_pv_finance(_with_tariff(base_input, loan_rate=0.0))
    res_expensive_loan = run_pv_finance(_with_tariff(base_input, loan_rate=15.0))
    # Loan rate below the discount rate adds leverage value; above it destroys value.
    assert res_cheap_loan.npv > base.npv > res_expensive_loan.npv

    res_no_debt = run_pv_finance(_with_tariff(base_input, debt_fraction=0.0))
    # Changing the debt fraction must change NPV (proves the param is live).
    assert res_no_debt.npv != pytest.approx(base.npv, rel=1e-4)


def test_netting_mode_affects_savings(base_tariff):
    """G10: hourly (net billing) vs monthly (net metering) must value energy differently.

    Uses a day-generation / night-heavy-load profile so export hours and import
    hours differ. Monthly net metering credits daytime exports against nighttime
    imports at the retail buy rate, so it is >= per-timestep net billing (hourly).
    """
    gen, load = [], []
    for h in range(8760):
        hod = h % 24
        gen.append(30.0 if 8 <= hod < 16 else 0.0)
        load.append(20.0 if (hod < 8 or hod >= 16) else 5.0)
    inp = FinanceInput(
        system_size_kw=100.0, production_series=gen,
        consumption_series=load, tariff=base_tariff,
    )
    hourly = run_pv_finance(inp, netting_mode="hourly")
    monthly = run_pv_finance(inp, netting_mode="monthly")

    assert hourly.annual_savings != pytest.approx(monthly.annual_savings, rel=1e-3)
    assert monthly.annual_savings >= hourly.annual_savings


def test_config_driven_degradation(base_input):
    """G10: PV degradation now lives in config; changing it changes outputs, no code change."""
    res_base = run_pv_finance(base_input)
    res_high_deg = run_pv_finance(_with_tariff(base_input, pv_degradation_rate=2.0))
    # Faster degradation → less lifetime energy → lower NPV, higher LCOE.
    assert res_high_deg.npv < res_base.npv
    assert res_high_deg.lcoe > res_base.lcoe
