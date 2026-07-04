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
    
    # If golden file does not exist or we want to overwrite it, we can create it
    # For now, we will update it dynamically in the test or read it
    if not os.path.exists(golden_path):
        with open(golden_path, "w") as f:
            f.write(result.model_dump_json(indent=4))
            
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
