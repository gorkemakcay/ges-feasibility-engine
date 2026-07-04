import pandas as pd
from typing import Optional

from gesfeas.input.models import SiteParameters
from gesfeas.production.models import ProductionResult
from gesfeas.finance.models import TariffConfig, BatteryConfig, FinanceInput, BatteryFinanceInput
from gesfeas.regulation.models import RegulationConfig, GroundMountEligibility

from gesfeas.finance.engine import run_pv_finance
from gesfeas.finance.battery import run_pv_storage_finance, generate_hourly_load_profile
from gesfeas.regulation.engine import evaluate_compliance

from .models import ScenarioResult

def compare_scenarios(
    site: SiteParameters,
    consumption_df: pd.DataFrame,
    production: ProductionResult,
    tariff_config: TariffConfig,
    battery_config: BatteryConfig,
    regulation_config: RegulationConfig,
    ground_mount_flags: Optional[GroundMountEligibility] = None
) -> ScenarioResult:
    """
    Runs and compares PV-only and PV+Storage scenarios side-by-side,
    evaluates regulation compliance for both, and returns a recommendation.
    """
    
    # Extract monthly consumption to generate hourly load profile
    if len(consumption_df) == 12:
        monthly_consumption = consumption_df['consumption_kwh'].tolist()
    else:
        # If hourly data is passed, group by month
        monthly_consumption = consumption_df.groupby(consumption_df.index.month)['consumption_kwh'].sum().tolist()
        
    hourly_load = generate_hourly_load_profile(monthly_consumption, site.shift_pattern)
    
    # ---------------------------------------------------------
    # 1. PV-Only Scenario
    # ---------------------------------------------------------
    pv_input = FinanceInput(
        system_size_kw=production.system_size_kwp,
        production_series=production.hourly_production_kwh,
        consumption_series=hourly_load,
        tariff=tariff_config
    )
    pv_only_result = run_pv_finance(pv_input)
    
    # Calculate self-consumption ratio for PV-only to feed into regulation check
    pv_to_load = sum(min(p, l) for p, l in zip(production.hourly_production_kwh, hourly_load))
    total_pv = sum(production.hourly_production_kwh)
    pv_only_self_consumption_ratio = pv_to_load / total_pv if total_pv > 0 else 0.0
    
    pv_only_compliance = evaluate_compliance(
        site=site,
        system_size_kw=production.system_size_kwp,
        self_consumption_ratio=pv_only_self_consumption_ratio,
        regulation_config=regulation_config,
        is_hybrid_storage=False,
        ground_mount_flags=ground_mount_flags
    )
    
    # ---------------------------------------------------------
    # 2. PV + Storage Scenario
    # ---------------------------------------------------------
    battery_input = BatteryFinanceInput(
        system_size_kw=production.system_size_kwp,
        production_series=production.hourly_production_kwh,
        monthly_consumption=monthly_consumption,
        shift_pattern=site.shift_pattern.value,
        tariff=tariff_config,
        battery=battery_config
    )
    pv_storage_result = run_pv_storage_finance(battery_input)
    
    pv_storage_compliance = evaluate_compliance(
        site=site,
        system_size_kw=production.system_size_kwp,
        self_consumption_ratio=pv_storage_result.self_consumption_ratio,
        regulation_config=regulation_config,
        is_hybrid_storage=True,
        ground_mount_flags=ground_mount_flags
    )
    
    # ---------------------------------------------------------
    # 3. Recommendation Logic
    # ---------------------------------------------------------
    if not pv_only_compliance.is_compliant and not pv_storage_compliance.is_compliant:
        recommendation = "Projeye Onay Verilmiyor"
        recommendation_rationale = "Hem sadece GES hem de GES+Depolama senaryoları mevcut EPDK regülasyonlarını ihlal etmektedir. Lütfen kapasiteyi düşürerek veya bağlantı tipini değiştirerek tekrar deneyin."
        
    elif not pv_storage_compliance.is_compliant:
        recommendation = "PV-only"
        recommendation_rationale = "PV+Storage is not compliant with current regulations. Recommending PV-only."
        
    elif not pv_only_compliance.is_compliant:
        # Extremely unlikely, but covered for completeness
        recommendation = "PV+Storage"
        recommendation_rationale = "PV-only is not compliant, but PV+Storage is. Recommending PV+Storage."
        
    else:
        # Both are compliant, compare financials
        if pv_only_result.npv >= pv_storage_result.npv:
            recommendation = "PV-only"
            recommendation_rationale = (
                f"PV-only has a better or equal NPV ({pv_only_result.npv:,.2f} USD) compared to "
                f"PV+Storage ({pv_storage_result.npv:,.2f} USD). Storage does not add enough financial value."
            )
        else:
            recommendation = "PV+Storage"
            recommendation_rationale = (
                f"PV+Storage has a better NPV ({pv_storage_result.npv:,.2f} USD) compared to "
                f"PV-only ({pv_only_result.npv:,.2f} USD). Battery storage adds financial value."
            )
            
    return ScenarioResult(
        pv_only=pv_only_result,
        pv_storage=pv_storage_result,
        pv_only_compliance=pv_only_compliance,
        pv_storage_compliance=pv_storage_compliance,
        recommendation=recommendation,
        recommendation_rationale=recommendation_rationale
    )
