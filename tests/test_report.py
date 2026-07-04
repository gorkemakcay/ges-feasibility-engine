import os
import pytest
import pandas as pd

from gesfeas.scenario.models import ScenarioResult
from gesfeas.finance.models import FinanceResult, BatteryFinanceResult, TariffConfig, BatteryConfig
from gesfeas.regulation.models import RegulationResult
from gesfeas.input.models import SiteParameters, Location, MountType, ShiftPattern, ConnectionType
from gesfeas.production.models import ProductionResult
from gesfeas.report.generator import generate_report_html, generate_report_pdf, generate_full_report


@pytest.fixture
def dummy_inputs():
    site = SiteParameters(
        location=Location(lat=39.9, lon=32.8),
        available_area_m2=1000.0,
        transformer_capacity_kva=400.0,
        mount_type=MountType.ROOFTOP,
        shift_pattern=ShiftPattern.SINGLE,
        connection_type=ConnectionType.ON_GRID
    )
    
    # Create dummy consumption dataframe
    consumption_df = pd.DataFrame({
        "consumption_kwh": [1000] * 12
    })
    
    production = ProductionResult(
        annual_energy_kwh=120000.0,
        capacity_factor=0.15,
        system_size_kwp=100.0,
        hourly_production_kwh=[0.0] * 8760
    )
    
    pv_only = FinanceResult(
        capex=50000.0,
        annual_savings=15000.0,
        npv=20000.0,
        lcoe=0.04,
        simple_payback=3.33,
        discounted_payback=4.5
    )
    
    pv_storage = BatteryFinanceResult(
        capex=80000.0,
        annual_savings=22000.0,
        npv=30000.0,
        lcoe=0.05,
        simple_payback=3.63,
        discounted_payback=4.8,
        self_consumption_ratio=0.8,
        grid_export_ratio=0.2,
        battery_cycles_year1=300.0
    )
    
    pv_only_compliance = RegulationResult(
        is_compliant=True,
        violations=[],
        warnings=["Some minor warning"]
    )
    
    pv_storage_compliance = RegulationResult(
        is_compliant=False,
        violations=["Battery capacity exceeds limits"],
        warnings=[]
    )
    
    scenario_result = ScenarioResult(
        pv_only=pv_only,
        pv_storage=pv_storage,
        pv_only_compliance=pv_only_compliance,
        pv_storage_compliance=pv_storage_compliance,
        recommendation="pv_only",
        recommendation_rationale="Storage is not compliant with current regulations."
    )
    
    return scenario_result, site, consumption_df, production


def test_generate_report_html(dummy_inputs, tmp_path):
    scenario_result, site, consumption_df, production = dummy_inputs
    
    html_content = generate_report_html(scenario_result, site, consumption_df, production)
    
    # Assert key sections exist
    assert "Güneş Enerjisi Santrali" in html_content
    assert "Yönetici Özeti" in html_content
    assert "Saha ve Tesis Bilgileri" in html_content
    assert "Tüketim Profili" in html_content
    assert "Üretim Tahmini" in html_content
    assert "Finansal Analiz (Sadece GES Senaryosu)" in html_content
    assert "Finansal Analiz (GES + Depolama Senaryosu)" in html_content
    assert "Senaryo Karşılaştırması" in html_content
    assert "Mevzuat ve Regülasyon Uyumluluğu" in html_content
    assert "Varsayımlar ve Yasal Uyarılar" in html_content
    
    # Assert values are rendered
    assert "Storage is not compliant with current regulations." in html_content
    assert "100.0" in html_content  # system size
    assert "50,000.00" in html_content  # capex
    
    # Save golden sample
    golden_dir = os.path.join(os.path.dirname(__file__), "golden")
    os.makedirs(golden_dir, exist_ok=True)
    golden_path = os.path.join(golden_dir, "g7_sample_report.html")
    with open(golden_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    assert os.path.exists(golden_path)


def test_generate_report_pdf(dummy_inputs, tmp_path):
    scenario_result, site, consumption_df, production = dummy_inputs
    
    html_content = generate_report_html(scenario_result, site, consumption_df, production)
    
    output_pdf = tmp_path / "test_report.pdf"
    
    generated_path = generate_report_pdf(html_content, str(output_pdf))
    
    assert os.path.exists(generated_path)
    assert os.path.getsize(generated_path) > 0
