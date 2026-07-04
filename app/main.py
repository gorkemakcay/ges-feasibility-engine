import os
import sys
import tempfile
import uuid
import yaml
import pandas as pd
import streamlit as st

# Add the project root to sys.path so we can import from src/gesfeas
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
src_dir = os.path.join(project_root, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from gesfeas.input.parser import parse_consumption_csv
from gesfeas.input.models import SiteParameters, Location, MountType, ShiftPattern, ConnectionType
from gesfeas.production.engine import run_production_model
from gesfeas.finance.models import TariffConfig, BatteryConfig
from gesfeas.regulation.models import RegulationConfig, GroundMountEligibility
from gesfeas.scenario.engine import compare_scenarios
from gesfeas.report.generator import generate_full_report

st.set_page_config(page_title="GES Feasibility Engine", layout="wide")

st.title("GES Feasibility Engine")
st.write("Calculate technical production, financial viability, and regulatory compliance for solar investments.")

# Configurations
CONFIG_DIR = os.path.join(project_root, "config")
TARIFF_FILE = os.path.join(CONFIG_DIR, "tariffs", "2026.yaml")
BATTERY_FILE = os.path.join(CONFIG_DIR, "tariffs", "battery_2026.yaml")
ROOFTOP_REG_FILE = os.path.join(CONFIG_DIR, "regulation", "rooftop.yaml")
GROUND_REG_FILE = os.path.join(CONFIG_DIR, "regulation", "ground_mount.yaml")

# Sidebar
st.sidebar.header("Site Parameters")

lat = st.sidebar.number_input("Latitude", value=39.93)
lon = st.sidebar.number_input("Longitude", value=32.85)
area = st.sidebar.number_input("Available Area (m²)", min_value=1.0, value=1000.0)
transformer_capacity = st.sidebar.number_input("Transformer Capacity (kVA)", min_value=1.0, value=400.0)
mount_type_str = st.sidebar.selectbox("Mount Type", ["Rooftop", "Ground"])
shift_pattern_str = st.sidebar.selectbox("Shift Pattern", ["Single", "Double", "Triple", "Weekend Closed"])
connection_type_str = st.sidebar.selectbox("Connection Type", ["On Grid", "Self Consumption Limited"])

mount_map = {"Rooftop": MountType.ROOFTOP, "Ground": MountType.GROUND}
shift_map = {"Single": ShiftPattern.SINGLE, "Double": ShiftPattern.DOUBLE, "Triple": ShiftPattern.TRIPLE, "Weekend Closed": ShiftPattern.WEEKEND_CLOSED}
conn_map = {"On Grid": ConnectionType.ON_GRID, "Self Consumption Limited": ConnectionType.SELF_CONSUMPTION_LIMITED}

mount_type = mount_map[mount_type_str]

ground_flags = None
if mount_type == MountType.GROUND:
    st.sidebar.subheader("Ground Mount Eligibility")
    ind_agr = st.sidebar.checkbox("Industrial or Agricultural Use", value=True)
    zoning = st.sidebar.checkbox("Zoning Status Approved", value=True)
    eia = st.sidebar.checkbox("EIA (ÇED) Approved", value=True)
    ground_flags = GroundMountEligibility(
        industrial_or_agricultural_use=ind_agr,
        zoning_status_approved=zoning,
        eia_approved=eia
    )

st.sidebar.header("System Size (Optional)")
use_custom_size = st.sidebar.checkbox("Specify System Size (kWp)?")
custom_system_size = None
if use_custom_size:
    custom_system_size = st.sidebar.number_input("System Size (kWp)", min_value=1.0, value=100.0)

st.sidebar.header("Consumption Data")
uploaded_csv = st.sidebar.file_uploader("Upload Consumption CSV", type=["csv"])

if st.button("Run Feasibility Analysis"):
    if uploaded_csv is None:
        st.error("Please upload a consumption CSV file.")
    else:
        with st.spinner("Running Pipeline... this may take a moment to fetch data and generate reports."):
            try:
                # 1. Parse Input
                with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                    tmp.write(uploaded_csv.getvalue())
                    tmp_csv_path = tmp.name
                
                try:
                    consumption_df = parse_consumption_csv(tmp_csv_path)
                finally:
                    os.unlink(tmp_csv_path)
                
                site = SiteParameters(
                    location=Location(lat=lat, lon=lon),
                    available_area_m2=area,
                    transformer_capacity_kva=transformer_capacity,
                    mount_type=mount_type,
                    shift_pattern=shift_map[shift_pattern_str],
                    connection_type=conn_map[connection_type_str]
                )
                
                # 2. Load Configs
                tariff_config = TariffConfig.from_yaml(TARIFF_FILE)
                battery_config = BatteryConfig.from_yaml(BATTERY_FILE)
                
                reg_file = ROOFTOP_REG_FILE if mount_type == MountType.ROOFTOP else GROUND_REG_FILE
                with open(reg_file, 'r', encoding='utf-8') as f:
                    reg_data = yaml.safe_load(f)
                reg_config = RegulationConfig(**reg_data)
                
                # 3. Production
                try:
                    production = run_production_model(site, custom_system_size)
                except Exception as p_err:
                    st.warning("Failed to fetch production data from PVGIS. Please check your internet connection and try again.")
                    raise p_err
                
                # 4. Scenario Comparison
                scenario_result = compare_scenarios(
                    site=site,
                    consumption_df=consumption_df,
                    production=production,
                    tariff_config=tariff_config,
                    battery_config=battery_config,
                    regulation_config=reg_config,
                    ground_mount_flags=ground_flags
                )
                
                # 5. Report Generation
                report_dir = os.path.join(tempfile.gettempdir(), "gesfeas_reports")
                os.makedirs(report_dir, exist_ok=True)
                report_path = os.path.join(report_dir, f"report_{uuid.uuid4().hex}.pdf")
                generate_full_report(scenario_result, site, consumption_df, production, report_path)
                
                # Display Results
                st.success("Analysis complete!")
                
                # Key Metrics
                st.header("Key Metrics")
                col1, col2, col3 = st.columns(3)
                col1.metric("System Size", f"{production.system_size_kwp:.1f} kWp")
                col2.metric("Annual Production", f"{production.annual_energy_kwh:,.0f} kWh")
                col3.metric("Capacity Factor", f"{production.capacity_factor*100:.1f}%")
                
                # Scenario Comparison
                st.header("Scenario Comparison")
                comp_data = {
                    "Metric": ["CAPEX (USD)", "NPV (USD)", "LCOE (USD/kWh)", "Payback (Yrs)"],
                    "PV Only": [
                        f"{scenario_result.pv_only.capex:,.0f}",
                        f"{scenario_result.pv_only.npv:,.0f}",
                        f"{scenario_result.pv_only.lcoe:.4f}",
                        f"{scenario_result.pv_only.simple_payback:.1f}"
                    ],
                    "PV + Storage": [
                        f"{scenario_result.pv_storage.capex:,.0f}",
                        f"{scenario_result.pv_storage.npv:,.0f}",
                        f"{scenario_result.pv_storage.lcoe:.4f}",
                        f"{scenario_result.pv_storage.simple_payback:.1f}"
                    ]
                }
                st.dataframe(pd.DataFrame(comp_data), hide_index=True)
                
                # Compliance Status
                st.header("Compliance Status")
                c1, c2 = st.columns(2)
                with c1:
                    st.subheader("PV Only")
                    if scenario_result.pv_only_compliance.is_compliant:
                        st.success("Compliant")
                    else:
                        st.error("Non-compliant")
                        for v in scenario_result.pv_only_compliance.violations:
                            st.write(f"- {v}")
                with c2:
                    st.subheader("PV + Storage")
                    if scenario_result.pv_storage_compliance.is_compliant:
                        st.success("Compliant")
                    else:
                        st.error("Non-compliant")
                        for v in scenario_result.pv_storage_compliance.violations:
                            st.write(f"- {v}")
                            
                # Recommendation
                st.header("Recommendation")
                st.info(f"**{scenario_result.recommendation}**\n\n{scenario_result.recommendation_rationale}")
                
                # Download Report
                st.header("Detailed Report")
                with open(report_path, "rb") as f:
                    st.download_button(
                        label="Download PDF Report",
                        data=f,
                        file_name="GES_Feasibility_Report.pdf",
                        mime="application/pdf"
                    )
                    
            except Exception as e:
                st.error(f"An error occurred during analysis: {str(e)}")
