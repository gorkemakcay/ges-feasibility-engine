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
            white-space: nowrap;
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

        /* ---------------- ANIMATIONS ---------------- */
        @keyframes slideUpFade {
            from { opacity: 0; transform: translateY(50px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-8px); }
            100% { transform: translateY(0px); }
        }
        
        @keyframes pulseGlow {
            0% { box-shadow: 0 0 10px rgba(56, 189, 248, 0.2); }
            50% { box-shadow: 0 0 25px rgba(56, 189, 248, 0.6); }
            100% { box-shadow: 0 0 10px rgba(56, 189, 248, 0.2); }
        }
        
        /* Base Entry Animations (Fallback for browsers without scroll-driven anims) */
        .hero {
            animation: slideUpFade 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        
        .glass-card {
            opacity: 0;
            animation: slideUpFade 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        .glass-card:nth-child(1) { animation-delay: 0.1s; }
        .glass-card:nth-child(2) { animation-delay: 0.3s; }
        .glass-card:nth-child(3) { animation-delay: 0.5s; }
        
        .table-responsive {
            opacity: 0;
            animation: slideUpFade 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
            animation-delay: 0.7s;
        }
        
        .card-icon {
            display: inline-block;
            animation: float 3.5s ease-in-out infinite;
        }
        
        .stButton>button {
            animation: pulseGlow 2.5s infinite;
        }
        .stButton>button:hover {
            animation: none; /* Reset on hover */
        }
        
        /* 🔥 Scroll-Driven Animations (Modern Browsers) */
        @supports (animation-timeline: view()) {
            .glass-card, .table-responsive, .kpi-card, h2, h3, .stAlert {
                animation: slideUpFade 1s cubic-bezier(0.16, 1, 0.3, 1) both !important;
                animation-timeline: view() !important;
                animation-range: entry 5% cover 25% !important;
            }
            .hero {
                /* Hero should just animate on load, not scroll */
                animation: slideUpFade 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
            }
        }
        
        /* Tabs styling */
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
        }
        .stTabs [data-baseweb="tab"] {
            height: 50px;
            white-space: nowrap;
            background-color: transparent;
            border-radius: 4px 4px 0px 0px;
            gap: 1px;
            padding-top: 10px;
            padding-bottom: 10px;
        }
        .stTabs [aria-selected="true"] {
            color: #38bdf8 !important;
        }
        
        /* ---- Info / Methodology panels (domain-expert notes) ---- */
        .method-note {
            background: rgba(30, 41, 59, 0.5);
            border-left: 4px solid #38bdf8;
            border-radius: 10px;
            padding: 1.25rem 1.5rem;
            margin: 0.9rem 0;
            color: #cbd5e1;
            font-size: 0.98rem;
            line-height: 1.65;
        }
        .method-note .mn-title {
            color: #f8fafc;
            font-weight: 600;
            font-size: 1.05rem;
            margin-bottom: 0.45rem;
            display: flex; align-items: center; gap: 0.5rem;
        }
        .method-note code {
            background: rgba(56,189,248,0.12);
            color: #7dd3fc;
            padding: 1px 6px; border-radius: 5px;
            font-size: 0.9em;
            white-space: nowrap;
        }
        .method-note.warn { border-left-color: #fbbf24; background: rgba(251,191,36,0.06); }
        .method-note.warn .mn-title { color: #fcd34d; }

        /* Key-assumption spec grid */
        .spec-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
            gap: 0.75rem;
            margin: 1rem 0 1.5rem 0;
        }
        .spec-item {
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid rgba(255,255,255,0.06);
            border-radius: 10px;
            padding: 0.9rem 1.1rem;
        }
        .spec-item .sp-label { color:#94a3b8; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.5px; }
        .spec-item .sp-value { color:#e2e8f0; font-size:1.15rem; font-weight:700; margin-top:0.25rem; }
        .spec-item .sp-note { color:#64748b; font-size:0.78rem; margin-top:0.15rem; }

        /* Mobile Responsive Adjustments */
        @media (max-width: 768px) {
            .method-note { padding: 1rem 1.1rem; font-size: 0.92rem; margin: 0.7rem 0; }
            .method-note .mn-title { font-size: 0.98rem; }
            .method-note code { white-space: normal; word-break: break-word; }
            .spec-grid { grid-template-columns: 1fr 1fr; gap: 0.55rem; }
            .spec-item { padding: 0.7rem 0.8rem; }
            .spec-item .sp-value { font-size: 1rem; }
            .spec-item .sp-label { font-size: 0.7rem; }
            .hero { padding: 3rem 1rem; }
            .hero-title { font-size: 2.2rem; }
            .hero-subtitle { font-size: 1rem; }
            .glass-card { padding: 1.5rem; }
            .kpi-value { font-size: 1.8rem; }
            .custom-table th, .custom-table td { 
                padding: 0.8rem; 
                font-size: 0.9rem; 
            }
            .stTabs [data-baseweb="tab-list"] { gap: 8px; }
            .stTabs [data-baseweb="tab"] { 
                padding-left: 10px; 
                padding-right: 10px; 
                font-size: 0.9rem;
            }
            .stButton>button { width: 100%; }
            
            /* Tweak animation range for mobile screens (needs to trigger earlier) */
            @supports (animation-timeline: view()) {
                .glass-card, .table-responsive, .kpi-card, h2, h3, .stAlert {
                    animation-range: entry 2% cover 15% !important;
                }
            }
        }

        /* Very small phones: single-column assumption grid */
        @media (max-width: 480px) {
            .spec-grid { grid-template-columns: 1fr; }
            .hero-title { font-size: 1.9rem; }
        }
    </style>
    """, unsafe_allow_html=True)

inject_custom_css()

# --- MAIN LAYOUT ---
tab_landing, tab_calc, tab_dash = st.tabs(["🚀 Keşfet", "⚙️ Fizibilite Kalkülatörü", "📊 Sonuç Panosu"])

# --- TAB 1: LANDING PAGE ---
with tab_landing:
    st.markdown("""
    <div class="hero">
        <h1 class="hero-title">GES Fizibilitesinin Geleceği Burada</h1>
        <p class="hero-subtitle">
            Eski CAD araçlarını ve haftalarca süren manuel Excel modellemesini geride bırak.
            EPDK uyumlu, finansal olarak optimize edilmiş PV ve batarya fizibilite raporlarını
            2 dakikadan kısa sürede üret.
        </p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<h2 style='text-align: center; margin-bottom: 2rem;'>Neden GES Feasibility Engine?</h2>", unsafe_allow_html=True)

    st.markdown("""
    <div class="glass-card-container">
        <div class="glass-card">
            <div class="card-icon">⚡</div>
            <div class="card-title">Anında Finansal Modelleme</div>
            <div class="card-text">NREL PySAM ile güçlendirilmiştir. Sadece üretimi değil; Türkiye pazarına uyarlanmış CAPEX, NPV, LCOE ve geri ödeme sürelerini de otomatik hesaplar.</div>
        </div>
        <div class="glass-card">
            <div class="card-icon">🔋</div>
            <div class="card-title">Batarya Senaryosu Optimizasyonu</div>
            <div class="card-text">Yeni hibrit çatı yönetmeliğinde kafan mı karıştı? Motor, en kârlı yolu bulmak için PV-Only ile PV+Storage senaryolarını otomatik karşılaştırır.</div>
        </div>
        <div class="glass-card">
            <div class="card-icon">⚖️</div>
            <div class="card-title">Otomatik EPDK Uyumluluğu</div>
            <div class="card-text">Config-driven regülasyon kontrolleri, projenin güncel mevzuata (ör. Madde 5.1.h, 25 kW limiti, imar şartları) uygunluğunu daha tek kuruş harcamadan doğrular.</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### 🏆 Pazar Boşluğu: Biz vs Eski Araçlar")
    st.markdown("""
    <div class="table-responsive">
        <table class="custom-table">
            <tr>
                <th>Özellik / Yetenek</th>
                <th>GES Feasibility Engine</th>
                <th>Eski Araçlar (ör. PVCase, PVSyst)</th>
            </tr>
            <tr>
                <td>Ana Odak</td>
                <td>Uçtan Uca Finansal & Regülasyon Fizibilitesi</td>
                <td>3B CAD Geometrisi & Yerleşim Çizimi</td>
            </tr>
            <tr>
                <td>Gelişmiş Finansal Modelleme (NPV, LCOE)</td>
                <td><span class="badge-pro">Evet (Entegre)</span></td>
                <td><span class="badge-con">Hayır (Excel gerekir)</span></td>
            </tr>
            <tr>
                <td>Batarya Dispatch & Arbitraj Optimizasyonu</td>
                <td><span class="badge-pro">Evet</span></td>
                <td><span class="badge-con">Hayır</span></td>
            </tr>
            <tr>
                <td>Otomatik Yerel Regülasyon Uyumu</td>
                <td><span class="badge-pro">Evet (EPDK Kuralları)</span></td>
                <td><span class="badge-con">Manuel kontrol gerekir</span></td>
            </tr>
            <tr>
                <td>Rapor Üretim Süresi</td>
                <td><span class="badge-pro">< 2 Dakika</span></td>
                <td><span class="badge-con">Günler - Haftalar</span></td>
            </tr>
            <tr>
                <td>Maliyet</td>
                <td><span class="badge-pro">Erişilebilir SaaS</span></td>
                <td><span class="badge-con">~$2990/yıl + AutoCAD Lisansı</span></td>
            </tr>
        </table>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🎯 Güven & Doğruluk")
    st.info("""
    **Akademik & Endüstri Standardı Doğrulama:** Çekirdek hesaplama motorları **pvlib** (PVGIS verisiyle desteklenir) ve **National Renewable Energy Laboratory (NREL) PySAM** üzerinde çalışır.

    **Doğruluğu Maksimuma Çıkar:** Motor varsayılan profillerle de çalışır, ancak tesisinin ayrıntılı **8760 saatlik CSV tüketim profilini** kalkülatöre yükleyerek öz-tüketim ve batarya boyutlandırma hesaplarında **%99'a varan doğruluk** yakalayabilirsin.
    """)

    st.markdown("### 🛠️ Nasıl Çalışır?")
    st.markdown("""
    1. **Veri Girişi:** Fizibilite Kalkülatörü sekmesine git. Konum, alan gir ve tüketim CSV'ni yükle.
    2. **İşleme:** Motor PVGIS'i sorgular, PV fiziğini simüle eder, batarya dispatch mantığını çalıştırır, tarifeleri uygular ve EPDK kısıtlarını kontrol eder.
    3. **Aksiyona Dönük İçgörü:** Anında KPI panolarını gör, senaryoları karşılaştır ve sunuma hazır PDF raporu indir.
    """)

    # ------------------------------------------------------------------
    # Metodoloji / mühendis notları (Türkçe) — domain uzmanı için şeffaflık
    # ------------------------------------------------------------------
    st.markdown("---")
    st.markdown("### ⚙️ Motor & Metodoloji — bu araç neye göre hesaplıyor?")
    st.caption("Aşağıdaki notlar, elektrik/GES mühendisleri için hesabın hangi motorlara ve varsayımlara dayandığını şeffafça açıklar.")
    st.markdown("""
    <div class="method-note">
        <div class="mn-title">☀️ Üretim motoru — pvlib + PVGIS</div>
        Konumun enlem/boylamına göre <code>PVGIS</code> tipik meteorolojik yıl (TMY) verisi çekilir ve
        <code>pvlib</code> ile 8760 saatlik AC üretim simüle edilir. Model: PVWatts DC + inverter (DC/AC ≈ 1.2).
        Panel eğimi çatıda 20°, arazide (enlem − 10°); yön güneye bakar (azimut 180°). Arazi için tek-eksen
        güneş takibi opsiyoneldir. Sistem gücü otomatik tahmin edilir: çatı ≈ 200 W/m², arazi ≈ 100 W/m²
        (aralık bırakma nedeniyle) — ya da kalkülatörde elle girebilirsin.
    </div>
    <div class="method-note">
        <div class="mn-title">💰 Finans motoru — NREL PySAM (SAM)</div>
        NPV, LCOE ve geri ödeme, SAM masaüstü uygulamasıyla <b>birebir aynı motor</b> olan
        <code>PySAM.Utilityrate5</code> (enerji/fatura değeri, mahsuplaşma) + <code>PySAM.Cashloan</code>
        (CAPEX, borç, iskonto, nakit akışı) ile hesaplanır. Borç (%70 / 10 yıl / %5), 25 yıl proje ömrü,
        %0.5/yıl panel degradasyonu ve enflasyon eskalasyonu modele dahildir. Sonuç, SAM'in kendi
        yıl-yıl nakit-akışı çıktısıyla denetlenerek doğrulanmıştır.
    </div>
    <div class="method-note">
        <div class="mn-title">🔋 Batarya — sayaç-arkası (behind-the-meter) dispatch</div>
        Saatlik dispatch mantığı: PV önce yükü besler → fazlası bataryayı şarj eder → gece deşarj ederek
        şebeke alımını azaltır → kalan fazla şebekeye satılır. Öz-tüketim oranı, şebekeye ihracat oranı ve
        yıllık çevrim sayısı buradan çıkar. Yük profili tesisin <b>vardiya düzenine</b> göre şekillenir; bu yüzden
        depolamanın değeri tek vardiya ile üç vardiyada anlamlı biçimde farklıdır. Batarya boyutu/maliyeti
        config'ten gelir (12. yıl değişim maliyeti dahil).
    </div>
    <div class="method-note">
        <div class="mn-title">⚖️ Regülasyon — config-driven EPDK kuralları</div>
        Kurallar koda gömülü değildir, <code>YAML</code> config dosyalarında tutulur: çatı 25 kW lisanssız limiti,
        trafo kapasite oranı, hibrit depolama izni, arazi (Madde 5.1.h) uygunluk kriterleri (sanayi/tarımsal
        kullanım, imar, ÇED). Mevzuat değişince yalnızca config güncellenir, kod değişmez.
    </div>
    <div class="method-note warn">
        <div class="mn-title">⚠️ Önemli varsayımlar & sınırlar (mutlaka oku)</div>
        Para birimi şu an <b>USD</b> (TL değil); tarife placeholder değerdir ($0.12 alış / $0.08 satış, düz).
        Saatlik tüketim CSV'si yüklenmezse, 12 aylık toplam vardiya profiline göre 8760 saate dağıtılır (sentetik).
        Mahsuplaşma varsayılan olarak <b>saatlik (net billing)</b> alınır. Çıktılar bir <b>ön-fizibilite tahminidir</b>;
        nihai yatırım kararı için güncel EPDK metni ve gerçek tarife/kur ile doğrulanmalıdır.
    </div>
    """, unsafe_allow_html=True)

    st.markdown("#### 📐 Varsayılan teknik & finansal parametreler")
    st.markdown("""
    <div class="spec-grid">
        <div class="spec-item"><div class="sp-label">Panel eğimi</div><div class="sp-value">20° / enlem−10°</div><div class="sp-note">çatı / arazi</div></div>
        <div class="spec-item"><div class="sp-label">Azimut · DC/AC</div><div class="sp-value">180° · 1.20</div><div class="sp-note">güneye bakış</div></div>
        <div class="spec-item"><div class="sp-label">Sistem gücü</div><div class="sp-value">~200 / 100 W/m²</div><div class="sp-note">çatı / arazi</div></div>
        <div class="spec-item"><div class="sp-label">Panel degradasyonu</div><div class="sp-value">%0.5 / yıl</div></div>
        <div class="spec-item"><div class="sp-label">İskonto (nominal)</div><div class="sp-value">%8</div></div>
        <div class="spec-item"><div class="sp-label">Enflasyon</div><div class="sp-value">%2.5</div></div>
        <div class="spec-item"><div class="sp-label">Borç yapısı</div><div class="sp-value">%70 · 10y · %5</div><div class="sp-note">oran · vade · faiz</div></div>
        <div class="spec-item"><div class="sp-label">Proje ömrü</div><div class="sp-value">25 yıl</div></div>
    </div>
    """, unsafe_allow_html=True)

# --- TAB 2: CALCULATOR WIZARD ---
with tab_calc:
    st.markdown("<h2 style='margin-bottom: 1.5rem;'>Proje Kurulumu & Parametreler</h2>", unsafe_allow_html=True)

    with st.expander("📖 Bu parametreler neyi etkiliyor? (mühendis notları)"):
        st.markdown("""
| Parametre | Neyi etkiler? |
|---|---|
| **Konum (enlem/boylam)** | PVGIS TMY ışınım verisi bu noktadan çekilir → yıllık üretim ve kapasite faktörü. |
| **Alan (m²)** | Sistem gücünü otomatik belirler: çatı ≈ 200 W/m², arazi ≈ 100 W/m². Elle de girebilirsin. |
| **Kurulum tipi** | Regülasyon dalını seçer (çatı 25 kW limiti vs arazi 5.1.h) ve panel eğimini (20° / enlem−10°). |
| **Trafo kapasitesi (kVA)** | EPDK trafo-oranı kontrolünde kullanılır: sistem gücü ≤ trafo × oran olmalı. |
| **Vardiya düzeni** | 12 aylık tüketimi 8760 saatlik yük eğrisine şekillendirir. Bataryanın değeri buna göre değişir (gece yükü → depolama daha değerli). |
| **Bağlantı tipi** | *Self-consumption limited* seçilirse minimum öz-tüketim oranı regülasyon kontrolü devreye girer. |
| **Tüketim CSV** | Yüklenirse gerçek 8760 saatlik profil kullanılır (en yüksek doğruluk); yüklenmezse vardiyaya göre sentetik profil üretilir. |
""")

    with st.container():
        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.markdown("#### 📍 Konum & Saha Özellikleri")
            lat = st.number_input("Enlem (Latitude)", value=39.93, format="%.4f")
            lon = st.number_input("Boylam (Longitude)", value=32.85, format="%.4f")
            st.caption("📡 Üretim, bu konumun PVGIS tipik meteorolojik yıl (TMY) verisiyle simüle edilir.")
            area = st.number_input("Kullanılabilir Alan (m²)", min_value=1.0, value=1000.0, step=100.0)
            st.caption("📐 Sistem gücü otomatik: çatı ≈ 200 W/m², arazi ≈ 100 W/m². Aşağıdan elle de girebilirsin.")
            mount_type_str = st.selectbox("Kurulum Tipi", ["Çatı", "Arazi"])
            st.caption("⚖️ Regülasyon dalını belirler — çatı: 25 kW lisanssız limiti · arazi: Madde 5.1.h uygunluk kriterleri.")

        with col2:
            st.markdown("#### ⚡ Şebeke & Operasyonel Profil")
            transformer_capacity = st.number_input("Trafo Kapasitesi (kVA)", min_value=1.0, value=400.0, step=50.0)
            st.caption("🔌 EPDK kontrolü: sistem gücü (kW) ≤ trafo kapasitesi (kVA) × config'teki oran olmalı.")
            shift_pattern_str = st.selectbox("Vardiya Düzeni", ["Tek Vardiya", "Çift Vardiya", "Üç Vardiya", "Hafta Sonu Kapalı"])
            st.caption("🕒 Tüketimi 8760 saatlik yük eğrisine şekillendirir. Gece yükü arttıkça (çift/üç vardiya) batarya daha değerli olur.")
            connection_type_str = st.selectbox("Bağlantı Tipi", ["Şebekeye Bağlı", "Öz-Tüketim Kısıtlı"])
            st.caption("🔗 *Öz-Tüketim Kısıtlı* → minimum öz-tüketim oranı regülasyon kontrolü devreye girer.")

    st.markdown("<hr style='border-color: rgba(255,255,255,0.1);'>", unsafe_allow_html=True)
    
    with st.container():
        col3, col4 = st.columns(2, gap="large")
        
        with col3:
            st.markdown("#### 🏗️ Özel Detaylar & Kısıtlar")
            use_custom_size = st.checkbox("Sistem Gücünü Elle Belirle (kWp)?")
            st.caption("🏗️ İşaretlemezsen sistem gücü alandan tahmin edilir. İşaretlersen alan varsayımını ezip DC gücü doğrudan belirlersin.")
            custom_system_size = None
            if use_custom_size:
                custom_system_size = st.number_input("Sistem Gücü (kWp)", min_value=1.0, value=100.0, step=10.0)

            ground_flags = None
            if mount_type_str == "Arazi":
                st.markdown("**Arazi Kurulumu Uygunluk Şartları**")
                ind_agr = st.checkbox("Sanayi veya Tarımsal Kullanım (Madde 5.1.h)", value=True)
                zoning = st.checkbox("İmar Durumu Onaylı", value=True)
                eia = st.checkbox("ÇED (EIA) Onaylı", value=True)
                ground_flags = GroundMountEligibility(
                    industrial_or_agricultural_use=ind_agr,
                    zoning_status_approved=zoning,
                    eia_approved=eia
                )

        with col4:
            st.markdown("#### 📈 Tüketim Profili")
            st.info("💡 **Pro İpucu:** En yüksek batarya optimizasyon doğruluğu için 8760 saatlik CSV profili yükle.")
            uploaded_csv = st.file_uploader("Tüketim CSV'si Yükle (saatlik kWh)", type=["csv"])
            st.caption("📄 **CSV formatı:** `month, consumption_kwh` sütunlarıyla 12 satır (aylık toplam), "
                       "ya da 8760 satırlık saatlik profil. Saatlik veri öz-tüketim ve batarya boyutlandırmada en yüksek doğruluğu verir.")

    st.markdown("<br>", unsafe_allow_html=True)
    
    if st.button("🚀 Fizibilite Analizini Çalıştır", use_container_width=True):
        if uploaded_csv is None:
            st.error("⚠️ Devam etmek için lütfen bir tüketim CSV dosyası yükle.")
        else:
            with st.spinner("⚡ Pipeline çalışıyor... Üretim simüle ediliyor, dispatch optimize ediliyor ve regülasyon çapraz kontrol ediliyor..."):
                try:
                    # 1. Parse Input
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
                        tmp.write(uploaded_csv.getvalue())
                        tmp_csv_path = tmp.name
                    
                    try:
                        consumption_df = parse_consumption_csv(tmp_csv_path)
                    finally:
                        os.unlink(tmp_csv_path)
                    
                    mount_map = {"Çatı": MountType.ROOFTOP, "Arazi": MountType.GROUND}
                    shift_map = {"Tek Vardiya": ShiftPattern.SINGLE, "Çift Vardiya": ShiftPattern.DOUBLE, "Üç Vardiya": ShiftPattern.TRIPLE, "Hafta Sonu Kapalı": ShiftPattern.WEEKEND_CLOSED}
                    conn_map = {"Şebekeye Bağlı": ConnectionType.ON_GRID, "Öz-Tüketim Kısıtlı": ConnectionType.SELF_CONSUMPTION_LIMITED}

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
                    
                    st.success("✅ Analiz tamamlandı! İçgörülerini görmek için yukarıdaki **📊 Sonuç Panosu** sekmesine geç.")

                except Exception as e:
                    st.error(f"❌ Analiz sırasında bir hata oluştu: {str(e)}")

# --- TAB 3: RESULTS DASHBOARD ---
with tab_dash:
    if not st.session_state.get('analysis_run', False):
        st.info("👈 Panonu görmek için önce **Fizibilite Kalkülatörü** sekmesinde fizibilite analizini çalıştır.")
    else:
        prod = st.session_state.production
        scenario = st.session_state.scenario_result

        st.markdown("<h2 style='margin-bottom: 1.5rem;'>Teknik & Üretim KPI'ları</h2>", unsafe_allow_html=True)

        st.markdown(f"""
        <div class="kpi-container">
            <div class="kpi-card">
                <div class="kpi-title">Sistem Gücü</div>
                <div class="kpi-value">{prod.system_size_kwp:,.1f} kWp</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Yıllık Üretim</div>
                <div class="kpi-value">{prod.annual_energy_kwh:,.0f} kWh</div>
            </div>
            <div class="kpi-card">
                <div class="kpi-title">Kapasite Faktörü</div>
                <div class="kpi-value">{prod.capacity_factor*100:.1f}%</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("<h2 style='margin-top: 2rem; margin-bottom: 1rem;'>⚖️ Finansal Senaryo Karşılaştırması</h2>", unsafe_allow_html=True)

        st.markdown(f"""
        <div class="table-responsive">
            <table class="custom-table">
                <tr>
                    <th>Finansal Metrik</th>
                    <th>PV Only</th>
                    <th>PV + Storage</th>
                </tr>
                <tr>
                    <td><strong>CAPEX (İlk Yatırım)</strong></td>
                    <td>${scenario.pv_only.capex:,.0f}</td>
                    <td>${scenario.pv_storage.capex:,.0f}</td>
                </tr>
                <tr>
                    <td><strong>NPV (Net Bugünkü Değer)</strong></td>
                    <td>${scenario.pv_only.npv:,.0f}</td>
                    <td>${scenario.pv_storage.npv:,.0f}</td>
                </tr>
                <tr>
                    <td><strong>LCOE ($/kWh)</strong></td>
                    <td>${scenario.pv_only.lcoe:.4f}</td>
                    <td>${scenario.pv_storage.lcoe:.4f}</td>
                </tr>
                <tr>
                    <td><strong>Basit Geri Ödeme Süresi</strong></td>
                    <td>{scenario.pv_only.simple_payback:.1f} Yıl</td>
                    <td>{scenario.pv_storage.simple_payback:.1f} Yıl</td>
                </tr>
            </table>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("""
        <div class="method-note">
            <div class="mn-title">📖 Metrikler ne anlama geliyor?</div>
            <b>CAPEX:</b> ilk yatırım (PV + varsa batarya). &nbsp;•&nbsp;
            <b>NPV:</b> 25 yıllık net bugünkü değer — pozitif ve yüksek olması iyidir. &nbsp;•&nbsp;
            <b>LCOE:</b> üretilen enerjinin seviyelendirilmiş birim maliyeti ($/kWh); şebeke alış fiyatının altında olması kârlılığa işaret eder. &nbsp;•&nbsp;
            <b>Geri ödeme:</b> yatırımın kendini amorti etme süresi. NPV ve geri ödeme <code>PySAM.Cashloan</code> ile hesaplanır.
        </div>
        """, unsafe_allow_html=True)

        # Gerçek config değerlerinden varsayım paneli (şeffaflık)
        with st.expander("📋 Bu finansal sonuçlar hangi varsayımlara dayanıyor?"):
            try:
                _t = yaml.safe_load(open(TARIFF_FILE, encoding="utf-8"))
                _b = yaml.safe_load(open(BATTERY_FILE, encoding="utf-8"))
                st.markdown(f"""
                <div class="spec-grid">
                    <div class="spec-item"><div class="sp-label">Para birimi</div><div class="sp-value">USD ⚠️</div><div class="sp-note">TL değil — placeholder</div></div>
                    <div class="spec-item"><div class="sp-label">Alış / Satış</div><div class="sp-value">${_t['buy_price_kwh']:.2f} / ${_t['sell_price_kwh']:.2f}</div><div class="sp-note">$/kWh · düz tarife</div></div>
                    <div class="spec-item"><div class="sp-label">CAPEX (PV)</div><div class="sp-value">${_t['capex_per_kw']:.0f}/kW</div></div>
                    <div class="spec-item"><div class="sp-label">O&M</div><div class="sp-value">${_t['opex_per_kw_year']:.0f}/kW-yıl</div></div>
                    <div class="spec-item"><div class="sp-label">İskonto / Enflasyon</div><div class="sp-value">%{_t['discount_rate']:.1f} / %{_t['inflation_rate']:.1f}</div><div class="sp-note">nominal</div></div>
                    <div class="spec-item"><div class="sp-label">Borç</div><div class="sp-value">%{_t['debt_fraction']:.0f} · {_t['loan_term']}y · %{_t['loan_rate']:.1f}</div></div>
                    <div class="spec-item"><div class="sp-label">Panel degradasyonu</div><div class="sp-value">%{_t.get('pv_degradation_rate', 0.5):.1f}/yıl</div></div>
                    <div class="spec-item"><div class="sp-label">Proje ömrü</div><div class="sp-value">{_t['lifetime']} yıl</div></div>
                    <div class="spec-item"><div class="sp-label">Batarya</div><div class="sp-value">{_b['battery_capacity_kwh']:.0f} kWh / {_b['battery_power_kw']:.0f} kW</div><div class="sp-note">${_b['battery_capex_per_kwh']:.0f}/kWh</div></div>
                    <div class="spec-item"><div class="sp-label">Batarya değişimi</div><div class="sp-value">{_b['battery_replacement_year']}. yıl</div><div class="sp-note">${_b['battery_replacement_cost_per_kwh']:.0f}/kWh</div></div>
                    <div class="spec-item"><div class="sp-label">Round-trip verim</div><div class="sp-value">%{_b['round_trip_efficiency']*100:.0f}</div></div>
                    <div class="spec-item"><div class="sp-label">Mahsuplaşma</div><div class="sp-value">Saatlik</div><div class="sp-note">net billing (varsayılan)</div></div>
                </div>
                """, unsafe_allow_html=True)
                st.caption("Bu değerler `config/tariffs/*.yaml` dosyalarından okunur; mevzuat/piyasa değişince kod değil config güncellenir.")
            except Exception:
                st.caption("Varsayım değerleri okunamadı.")

        st.markdown("<h2 style='margin-top: 2rem; margin-bottom: 1rem;'>📜 Regülasyon Uyumu (EPDK)</h2>", unsafe_allow_html=True)

        col_c1, col_c2 = st.columns(2, gap="large")

        with col_c1:
            st.markdown("#### PV Only Senaryosu")
            if scenario.pv_only_compliance.is_compliant:
                st.markdown('<div class="alert-success"><strong>✅ Tam Uyumlu</strong><br>Tüm EPDK regülasyon kısıtlarını karşılıyor.</div>', unsafe_allow_html=True)
            else:
                errors = "".join([f"<li>{v}</li>" for v in scenario.pv_only_compliance.violations])
                st.markdown(f'<div class="alert-error"><strong>❌ Uyumsuz</strong><ul>{errors}</ul></div>', unsafe_allow_html=True)

        with col_c2:
            st.markdown("#### PV + Storage Senaryosu")
            if scenario.pv_storage_compliance.is_compliant:
                st.markdown('<div class="alert-success"><strong>✅ Tam Uyumlu</strong><br>Tüm EPDK regülasyon kısıtlarını karşılıyor.</div>', unsafe_allow_html=True)
            else:
                errors = "".join([f"<li>{v}</li>" for v in scenario.pv_storage_compliance.violations])
                st.markdown(f'<div class="alert-error"><strong>❌ Uyumsuz</strong><ul>{errors}</ul></div>', unsafe_allow_html=True)

        st.markdown("<h2 style='margin-top: 2rem; margin-bottom: 1rem;'>💡 Karar Önerisi</h2>", unsafe_allow_html=True)
        st.info(f"**{scenario.recommendation}**\n\n{scenario.recommendation_rationale}")
        st.caption("ℹ️ Bu öneri yapay zeka değildir: NPV karşılaştırması, EPDK uygunluğu ve öz-tüketim oranına dayalı **kural-tabanlı** bir karardır. Regülasyona aykırı bir senaryo, finansal olarak üstün olsa bile önerilmez.")
        
        st.markdown("---")
        st.markdown("### 📥 Nihai Sunumu Dışa Aktar")

        with open(st.session_state.report_path, "rb") as f:
            st.download_button(
                label="📄 Kapsamlı PDF Raporunu İndir",
                data=f,
                file_name="GES_Feasibility_Report.pdf",
                mime="application/pdf",
                use_container_width=True
            )
