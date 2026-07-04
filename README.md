# GES Fizibilite Motoru (GES Feasibility Engine)

Otonom ve yapılandırılabilir bir Güneş Enerjisi Santrali fizibilite aracı. 
Çatı ve arazi kurulumları için PV-Only (Sadece Güneş) ve PV+Storage (Batarya Depolamalı) senaryolarını hesaplar, 
Türkiye EPDK yönetmeliklerine uygunluğunu analiz eder ve WeasyPrint ile PDF rapor üretir.

## Mimari
- **Girdi:** Tüketim CSV, saha parametreleri, lokasyon.
- **Üretim Motoru:** `pvlib` (PVGIS verisi ile saatlik üretim).
- **Finans Motoru:** `nrel-pysam` (CAPEX, NPV, LCOE, batarya deşarj).
- **Regülasyon Motoru:** YAML config tabanlı kurallar.
- **Arayüz:** Streamlit MVP.

## Kurulum ve Çalıştırma

Gereksinimler: Python 3.11+ ve `uv`.

```bash
uv sync
uv run streamlit run app/main.py
```

## Testler

Projeyi ve kuralları doğrulamak için:
```bash
uv run pytest
```
