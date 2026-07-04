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

# Configurations
CONFIG_DIR = os.path.join(project_root, "config")
TARIFF_FILE = os.path.join(CONFIG_DIR, "tariffs", "2026.yaml")
BATTERY_FILE = os.path.join(CONFIG_DIR, "tariffs", "battery_2026.yaml")
ROOFTOP_REG_FILE = os.path.join(CONFIG_DIR, "regulation", "rooftop.yaml")
GROUND_REG_FILE = os.path.join(CONFIG_DIR, "regulation", "ground_mount.yaml")

# --- UI / UX CONFIGURATION ---
st.set_page_config(
    page_title="GES Feasibility Engine | Enterprise SaaS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

def inject_custom_css():
    st.markdown("""
    <style>
        /* Import premium font */
        @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Outfit', sans-serif !important;
            color: #e2e8f0;
        }
        
        /* Hide default Streamlit elements */
        #MainMenu {visibility: hidden;}
        header {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Hero Section */
        .hero {
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            padding: 5rem 2rem;
            border-radius: 20px;
            text-align: center;
            box-shadow: 0 20px 40px rgba(0,0,0,0.5);
            border: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 2rem;
            position: relative;
            overflow: hidden;
        }
        
        .hero::before {
            content: '';
            position: absolute;
            top: -50%; left: -50%;
            width: 200%; height: 200%;
            background: radial-gradient(circle, rgba(56, 189, 248, 0.1) 0%, transparent 50%);
            pointer-events: none;
        }
        
        .hero-title {
            font-size: 4rem;
            font-weight: 800;
            background: linear-gradient(to right, #38bdf8, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 1rem;
            line-height: 1.1;
        }
        
        .hero-subtitle {
            font-size: 1.25rem;
            color: #94a3b8;
            font-weight: 300;
            max-width: 800px;
            margin: 0 auto 2rem auto;
            line-height: 1.6;
        }
        
        /* Glassmorphism Cards */
        .glass-card-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
        }
        
        .glass-card {
            background: rgba(30, 41, 59, 0.6);
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            border-radius: 16px;
            padding: 2rem;
            transition: all 0.3s ease;
        }
        
        .glass-card:hover {
            transform: translateY(-5px);
            border-color: rgba(56, 189, 248, 0.4);
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            background: rgba(30, 41, 59, 0.8);
        }
        
        .card-icon {
            font-size: 2.5rem;
            margin-bottom: 1rem;
        }
        
        .card-title {
            font-size: 1.25rem;
            font-weight: 600;
            color: #f8fafc;
            margin-bottom: 0.75rem;
        }
        
        .card-text {
            color: #94a3b8;
            font-size: 1rem;
            line-height: 1.6;
        }

        /* KPI Dashboard Cards */
        .kpi-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1rem;
            margin-bottom: 2rem;
        }
        .kpi-card {
            background: linear-gradient(145deg, #1e293b, #0f172a);
            border-radius: 12px;
            padding: 1.5rem;
            border: 1px solid rgba(255, 255, 255, 0.05);
            text-align: center;
        }
        .kpi-title {
            color: #94a3b8;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 0.5rem;
        }
        .kpi-value {
            font-size: 2.2rem;
            font-weight: 800;
            color: #38bdf8;
        }
        
        /* Table Styles */
        .table-responsive {
            overflow-x: auto;
        }
        .custom-table {
            width: 100%;
            border-collapse: collapse;
            color: #f8fafc;
            margin: 1.5rem 0;
            background: rgba(30, 41, 59, 0.4);
            border-radius: 12px;
            overflow: hidden;
        }
        .custom-table th, .custom-table td {
            padding: 1.2rem;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .custom-table th {
            font-weight: 600;
            color: #818cf8;
            background: rgba(15, 23, 42, 0.8);
            font-size: 1.1rem;
        }
        .custom-table tr:hover {
            background: rgba(255,255,255,0.02);
        }
        .badge-pro { background: rgba(16, 185, 129, 0.2); color: #34d399; padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: 600; border: 1px solid rgba(16, 185, 129, 0.3);}
        .badge-con { background: rgba(239, 68, 68, 0.2); color: #f87171; padding: 4px 10px; border-radius: 12px; font-size: 0.85rem; font-weight: 600; border: 1px solid rgba(239, 68, 68, 0.3);}

        /* Alert boxes */
        .alert-success {
            background: rgba(16, 185, 129, 0.1);
            border-left: 4px solid #10b981;
            padding: 1.5rem;
            border-radius: 8px;
            color: #10b981;
            margin-top: 1rem;
        }
        .alert-error {
            background: rgba(239, 68, 68, 0.1);
            border-left: 4px solid #ef4444;
            padding: 1.5rem;
            border-radius: 8px;
            color: #ef4444;
            margin-top: 1rem;
        }
        .alert-error ul {
            margin-top: 0.5rem;
            margin-bottom: 0;
            padding-left: 1.5rem;
        }
        
        /* Button Glow */
        .stButton>button {
            background: linear-gradient(135deg, #38bdf8, #818cf8);
            color: white;
            font-weight: 600;
            font-size: 1.1rem;
            border: none;
            padding: 0.75rem 2rem;
            border-radius: 8px;
            transition: all 0.3s;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .stButton>button:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 25px rgba(56, 189, 248, 0.4);
            color: white;
            border-color: rgba(255,255,255,0.3);
        }
        
        .stDownloadButton>button {
            background: linear-gradient(135deg, #10b981, #059669);
            color: white;
            font-weight: 600;
            width: 100%;
            border-radius: 8px;
            border: none;
        }
        .stDownloadButton>button:hover {
            box-shadow: 0 10px 25px rgba(16, 185, 129, 0.4);
            color: white;
        }

        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: pre-wrap;
            background-color: transparent;
            border-radius: 4px 4px 0px 0px;
            gap: 1px;
            padding-top: 10px;
            padding-bottom: 10px;
        }
        .stTabs [aria-selected="true"] {
            color: #38bdf8 !important;
        }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- MAIN LAYOUT ---
tab_landing, tab_calc, tab_dash = st.tabs(["🚀 Discover", "⚙️ Feasibility Calculator", "📊 Results Dashboard"])

# --- TAB 1: LANDING PAGE ---
with tab_landing:
    st.markdown("""
    <div class="hero">
        <h1 class="hero-title">The Future of Solar Feasibility is Here</h1>
        <p class="hero-subtitle">
            Skip the legacy CAD tools and weeks of manual Excel modeling. Generate 
            EPDK-compliant, financially optimized PV and Battery feasibility reports 
            in under 2 minutes.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("<h2 style='text-align: center; margin-bottom: 2rem;'>Why Choose GES Feasibility Engine?</h2>", unsafe_allow_html=True)
    
    st.markdown("""
    <div class="glass-card-container">
        <div class="glass-card">
            <div class="card-icon">⚡</div>
            <div class="card-title">Instant Financial Modeling</div>
            <div class="card-text">Powered by NREL PySAM. We don't just calculate generation; we automatically compute CAPEX, NPV, LCOE, and Payback periods tailored for the Turkish market.</div>
        </div>
        <div class="glass-card">
            <div class="card-icon">🔋</div>
            <div class="card-title">Battery Scenario Optimization</div>
            <div class="card-text">Confused about the recent hybrid rooftop regulations? Our engine automatically compares PV-Only against PV+Storage to find your most profitable path.</div>
        </div>
        <div class="glass-card">
            <div class="card-icon">⚖️</div>
            <div class="card-title">Automated EPDK Compliance</div>
            <div class="card-text">Config-driven regulation checks ensure your project complies with the latest laws (e.g., Article 5.1.h, 25kW limits, zoning requirements) before you spend a dime.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🏆 Market Gap: Us vs Legacy Tools")
    st.markdown("""
    <div class="table-responsive">
        <table class="custom-table">
            <tr>
                <th>Feature / Capability</th>
                <th>GES Feasibility Engine</th>
                <th>Legacy Tools (e.g., PVCase, PVSyst)</th>
            </tr>
            <tr>
                <td>Primary Focus</td>
                <td>End-to-End Financial & Regulatory Feasibility</td>
                <td>3D CAD Geometry & Layout Drafting</td>
            </tr>
            <tr>
                <td>Advanced Financial Modeling (NPV, LCOE)</td>
                <td><span class="badge-pro">Yes (Integrated)</span></td>
                <td><span class="badge-con">No (Requires Excel)</span></td>
            </tr>
            <tr>
                <td>Battery Dispatch & Arbitrage Optimization</td>
                <td><span class="badge-pro">Yes</span></td>
                <td><span class="badge-con">No</span></td>
            </tr>
            <tr>
                <td>Automated Local Regulation Compliance</td>
                <td><span class="badge-pro">Yes (EPDK Rules)</span></td>
                <td><span class="badge-con">Manual checks required</span></td>
            </tr>
            <tr>
                <td>Report Generation Time</td>
                <td><span class="badge-pro">< 2 Minutes</span></td>
                <td><span class="badge-con">Days to Weeks</span></td>
            </tr>
            <tr>
                <td>Cost</td>
                <td><span class="badge-pro">Accessible SaaS</span></td>
                <td><span class="badge-con">~$2990/yr + AutoCAD License</span></td>
            </tr>
        </table>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🎯 Trust & Accuracy")
    st.info("""
    **Academic & Industry Standard Validation:** Our core calculation engines run on **pvlib** (supported by PVGIS data) and the **National Renewable Energy Laboratory's (NREL) PySAM**. 
    
    **Maximize Your Accuracy:** While the engine works with default profiles, you can achieve **up to 99% accuracy** in self-consumption and battery sizing calculations by uploading your facility's granular **8760-hour CSV consumption profile** in the calculator.
    """)

    st.markdown("### 🛠️ How It Works")
    st.markdown("""
    1. **Input Data:** Go to the Feasibility Calculator tab. Enter location, area, and upload your consumption CSV.
    2. **AI Processing:** The engine queries PVGIS, simulates physics, dispatches battery storage logic, applies Turkish tariffs, and checks EPDK constraints.
    3. **Actionable Insights:** Instantly view KPI dashboards, compare scenarios, and download a presentation-ready PDF report.
    """)

# --- TAB 2: CALCULATOR WIZARD ---
with tab_calc:
    st.markdown("<h2 style='margin-bottom: 1.5rem;'>Project Setup & Parameters</h2>", unsafe_allow_html=True)
    
    with st.container():
        col1, col2 = st.columns(2, gap="large")
        
        with col1:
            st.markdown("#### 📍 Location & Site Characteristics")
            lat = st.number_input("Latitude", value=39.93, format="%.4f")
            lon = st.number_input("Longitude", value=32.85, format="%.4f")
            area = st.number_input("Available Area (m²)", min_value=1.0, value=1000.0, step=100.0)
            mount_type_str = st.selectbox("Mount Type", ["Rooftop", "Ground"])
            
        with col2:
            st.markdown("#### ⚡ Grid & Operational Profile")
            transformer_capacity = st.number_input("Transformer Capacity (kVA)", min_value=1.0, value=400.0, step=50.0)
            shift_pattern_str = st.selectbox("Shift Pattern", ["Single", "Double", "Triple", "Weekend Closed"])
            connection_type_str = st.selectbox("Connection Type", ["On Grid", "Self Consumption Limited"])

    st.markdown("<hr style='border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
    
    with st.container():
        col3, col4 = st.columns(2, gap="large")
        
        with col3:
            st.markdown("#### 🏗️ Specific Details & Constraints")
            use_custom_size = st.checkbox("Specify Custom System Size (kWp)?")
            custom_system_size = None
            if use_custom_size:
                custom_system_size = st.number_input("System Size (kWp)", min_value=1.0, value=100.0, step=10.0)
                
            ground_flags = None
            if mount_type_str == "Ground":
                st.markdown("**Ground Mount Eligibility Requirements**")
                ind_agr = st.checkbox("Industrial or Agricultural Use (Art 5.1.h)", value=True)
                zoning = st.checkbox("Zoning Status Approved", value=True)
                eia = st.checkbox("EIA (ÇED) Approved", value=True)
                ground_flags = GroundMountEligibility(
                    industrial_or_agricultural_use=ind_agr,
                    zoning_status_approved=zoning,
                    eia_approved=eia
                )
                
        with col4:
            st.markdown("#### 📈 Consumption Profile")
            st.info("💡 **Pro Tip:** Upload an 8760-hour CSV profile for highest accuracy in battery optimization.")
            uploaded_csv = st.file_uploader("Upload Consumption CSV (kW/h per hour)", type=["csv"])

    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🚀 Run Feasibility Analysis", use_container_width=True):
        if uploaded_csv is None:
            st.error("⚠️ Please upload a consumption CSV file to proceed.")
        else:
            with st.spinner("⚡ Running AI Pipeline... Generating Models, Optimizing Dispatch, and Cross-checking Regulations..."):
                try:
                    # 1. Parse Input
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                        tmp.write(uploaded_csv.getvalue())
                        tmp_csv_path = tmp.name
                    
                    try:
                        consumption_df = parse_consumption_csv(tmp_csv_path)
                    finally:
                        os.unlink(tmp_csv_path)
                    
                    mount_map = {"Rooftop": MountType.ROOFTOP, "Ground": MountType.GROUND}
                    shift_map = {"Single": ShiftPattern.SINGLE, "Double": ShiftPattern.DOUBLE, "Triple": ShiftPattern.TRIPLE, "Weekend Closed": ShiftPattern.WEEKEND_CLOSED}
                    conn_map = {"On Grid": ConnectionType.ON_GRID, "Self Consumption Limited": ConnectionType.SELF_CONSUMPTION_LIMITED}

                    site = SiteParameters(
                        location=Location(lat=lat, lon=lon),
                        available_area_m2=area,
                        transformer_capacity_kva=transformer_capacity,
                        mount_type=mount_map[mount_type_str],
                        shift_pattern=shift_map[shift_pattern_str],
                        connection_type=conn_map[connection_type_str]
                    )
                    
                    # 2. Load Configs
                    tariff_config = TariffConfig.from_yaml(TARIFF_FILE)
                    battery_config = BatteryConfig.from_yaml(BATTERY_FILE)
                    
                    reg_file = ROOFTOP_REG_FILE if site.mount_type == MountType.ROOFTOP else GROUND_REG_FILE
                    with open(reg_file, 'r', encoding='utf-8') as f:
                        reg_data = yaml.safe_load(f)
                    reg_config = RegulationConfig(**reg_data)
                    
                    # 3. Production
                    production = run_production_model(site, custom_system_size)
                    
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
                    
                    # Save state
                    st.session_state.analysis_run = True
                    st.session_state.scenario_result = scenario_result
                    st.session_state.production = production
                    st.session_state.report_path = report_path
                    
                    st.success("✅ Analysis complete! Please navigate to the **📊 Results Dashboard** tab above to view your insights.")
                    
                except Exception as e:
                    st.error(f"❌ An error occurred during analysis: {str(e)}")

# --- TAB 3: RESULTS DASHBOARD ---
with tab_dash:
    if not st.session_state.get('analysis_run', False):
        st.info("👈 Please run the feasibility analysis in the **Feasibility Calculator** tab first to see your dashboard.")
    else:
        prod = st.session_state.production
        scenario = st.session_state.scenario_result
        
        st.markdown("<h2 style='margin-bottom: 1.5rem;'>Technical & Production KPIs</h2>", unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-title">System Size</div>
                <div class="kpi-value">{prod.system_size_kwp:,.1f} kWp</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Annual Generation</div>
                <div class="kpi-value">{prod.annual_energy_kwh:,.0f} kWh</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Capacity Factor</div>
                <div class="kpi-value">{prod.capacity_factor*100:.1f}%</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h2 style='margin-top: 2rem; margin-bottom: 1rem;'>⚖️ Financial Scenario Comparison</h2>", unsafe_allow_html=True)
        
        st.markdown(f"""
        <div class="table-responsive">
            <table class="custom-table">
                <tr>
                    <th>Financial Metric</th>
                    <th>PV Only</th>
                    <th>PV + Storage</th>
                </tr>
                <tr>
                    <td><strong>CAPEX (Initial Investment)</strong></td>
                    <td>${scenario.pv_only.capex:,.0f}</td>
                    <td>${scenario.pv_storage.capex:,.0f}</td>
                </tr>
                <tr>
                    <td><strong>NPV (Net Present Value)</strong></td>
                    <td>${scenario.pv_only.npv:,.0f}</td>
                    <td>${scenario.pv_storage.npv:,.0f}</td>
                </tr>
                <tr>
                    <td><strong>LCOE ($/kWh)</strong></td>
                    <td>${scenario.pv_only.lcoe:.4f}</td>
                    <td>${scenario.pv_storage.lcoe:.4f}</td>
                </tr>
                <tr>
                    <td><strong>Simple Payback Period</strong></td>
                    <td>{scenario.pv_only.simple_payback:.1f} Years</td>
                    <td>{scenario.pv_storage.simple_payback:.1f} Years</td>
                </tr>
            </table>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h2 style='margin-top: 2rem; margin-bottom: 1rem;'>📜 Regulatory Compliance (EPDK)</h2>", unsafe_allow_html=True)
        
        col_c1, col_c2 = st.columns(2, gap="large")
        
        with col_c1:
            st.markdown("#### PV Only Scenario")
            if scenario.pv_only_compliance.is_compliant:
                st.markdown('<div class="alert-success"><strong>✅ Fully Compliant</strong><br>Meets all EPDK regulation constraints.</div>', unsafe_allow_html=True)
            else:
                errors = "".join([f"<li>{v}</li>" for v in scenario.pv_only_compliance.violations])
                st.markdown(f'<div class="alert-error"><strong>❌ Non-Compliant</strong><ul>{errors}</ul></div>', unsafe_allow_html=True)

        with col_c2:
            st.markdown("#### PV + Storage Scenario")
            if scenario.pv_storage_compliance.is_compliant:
                st.markdown('<div class="alert-success"><strong>✅ Fully Compliant</strong><br>Meets all EPDK regulation constraints.</div>', unsafe_allow_html=True)
            else:
                errors = "".join([f"<li>{v}</li>" for v in scenario.pv_storage_compliance.violations])
                st.markdown(f'<div class="alert-error"><strong>❌ Non-Compliant</strong><ul>{errors}</ul></div>', unsafe_allow_html=True)

        st.markdown("<h2 style='margin-top: 2rem; margin-bottom: 1rem;'>💡 AI Recommendation</h2>", unsafe_allow_html=True)
        st.info(f"**{scenario.recommendation}**\n\n{scenario.recommendation_rationale}")
        
        st.markdown("---")
        st.markdown("### 📥 Export Final Presentation")
        
        with open(st.session_state.report_path, "rb") as f:
            st.download_button(
                label="📄 Download Comprehensive PDF Report",
                data=f,
                file_name="GES_Feasibility_Report.pdf",
                mime="application/pdf",
                use_container_width=True
            )
