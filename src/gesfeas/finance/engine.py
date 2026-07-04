import PySAM.Lcoefcr as lcoe
from typing import List
from .models import FinanceInput, FinanceResult

def run_pv_finance(inputs: FinanceInput) -> FinanceResult:
    """
    Runs a PV-ONLY techno-economic model via NREL-PySAM LCOE calculator
    and standard NPV/payback calculation for behind-the-meter.
    """
    t = inputs.tariff
    sys_kw = inputs.system_size_kw
    gen = inputs.production_series
    load = inputs.consumption_series if inputs.consumption_series else [0.0] * len(gen)

    # 1. CAPEX
    capex = sys_kw * t.capex_per_kw
    
    # 2. Annual Generation and Revenue/Savings (Year 1)
    # Behind-the-meter logic: self-consumed displaces buy_price, excess is sold at sell_price
    year1_savings = 0.0
    year1_gen = 0.0
    for g, l in zip(gen, load):
        year1_gen += g
        self_consumed = min(g, l)
        exported = max(g - l, 0.0)
        year1_savings += (self_consumed * t.buy_price_kwh) + (exported * t.sell_price_kwh)

    # 3. NREL-PySAM LCOE calculation (using Lcoefcr)
    m_lcoe = lcoe.new()
    m_lcoe.SimpleLCOE.capital_cost = capex
    m_lcoe.SimpleLCOE.fixed_operating_cost = sys_kw * t.opex_per_kw_year
    m_lcoe.SimpleLCOE.variable_operating_cost = 0.0
    # Fixed charge rate approx: PMT function
    rate = t.discount_rate / 100.0
    if rate > 0:
        fcr = rate / (1 - (1 + rate) ** -t.lifetime)
    else:
        fcr = 1.0 / t.lifetime
    m_lcoe.SimpleLCOE.fixed_charge_rate = fcr
    m_lcoe.SimpleLCOE.annual_energy = year1_gen
    m_lcoe.execute()
    lcoe_val = m_lcoe.Outputs.lcoe_fcr

    # 4. Cash Flow, NPV, and Payback
    cash_flows = [-capex]
    inflation = t.inflation_rate / 100.0
    discount = t.discount_rate / 100.0
    degradation = 0.005 # 0.5% per year assumed

    npv = -capex
    cumulative_cash = -capex
    cumulative_disc_cash = -capex
    
    simple_payback = -1.0
    discounted_payback = -1.0
    
    for year in range(1, t.lifetime + 1):
        # Escalate savings and O&M
        current_savings = year1_savings * ((1 - degradation) ** (year - 1)) * ((1 + inflation) ** (year - 1))
        current_opex = (sys_kw * t.opex_per_kw_year) * ((1 + inflation) ** (year - 1))
        
        net_cf = current_savings - current_opex
        cash_flows.append(net_cf)
        
        disc_cf = net_cf / ((1 + discount) ** year)
        npv += disc_cf
        
        # Track payback
        if cumulative_cash < 0 and cumulative_cash + net_cf >= 0 and simple_payback < 0:
            simple_payback = (year - 1) + abs(cumulative_cash) / net_cf
        cumulative_cash += net_cf
        
        if cumulative_disc_cash < 0 and cumulative_disc_cash + disc_cf >= 0 and discounted_payback < 0:
            discounted_payback = (year - 1) + abs(cumulative_disc_cash) / disc_cf
        cumulative_disc_cash += disc_cf

    return FinanceResult(
        capex=capex,
        annual_savings=year1_savings,
        npv=npv,
        lcoe=lcoe_val,
        simple_payback=simple_payback if simple_payback > 0 else t.lifetime,
        discounted_payback=discounted_payback if discounted_payback > 0 else t.lifetime
    )
