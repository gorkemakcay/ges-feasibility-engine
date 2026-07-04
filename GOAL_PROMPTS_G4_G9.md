# Goal Prompts: G4 – G9

> Bu dosya, G0–G3 ile kurulan kalıbı takip ederek G4'ten G9'a kadar her otonom oturum için kopyala-yapıştır talimatları içerir.
> Her promptu yeni bir oturumun başında olduğu gibi kullanın.

---

## G4 — Battery Scenario (PySAM, PV + Storage)

```
You are implementing GOAL G4 (Battery / PV+Storage scenario) of the GES feasibility engine. Read AGENTS.md and PROJECT_BRIEF.md first. Do ONLY G4. Do not touch other modules.

Scope (in src/gesfeas/finance/):
- Extend the existing finance module to support a PV + battery-storage scenario, alongside the current PV-only path.
- Add battery-specific configuration to config/tariffs/ (battery CAPEX $/kWh, battery capacity kWh, battery power kW, round-trip efficiency, degradation rate, replacement year/cost). Keep it config-driven — NEVER hardcode battery cost or sizing assumptions.
- Implement battery dispatch logic for behind-the-meter self-consumption optimization: charge from excess PV, discharge to offset grid purchases during non-solar hours.
- The dispatch must be aware of the facility's shift_pattern (from src/gesfeas/input/models.py → ShiftPattern). A triple-shift (24h) facility has very different storage value than a single-shift (daytime-only) facility. Generate an hourly load profile from the monthly consumption totals using the shift_pattern enum to shape the 8760 load curve.
- Compute the same financial outputs as G3 (CAPEX, annual_savings, NPV, LCOE, simple_payback, discounted_payback) but for the PV+Storage case. Add storage-specific metrics: self_consumption_ratio, grid_export_ratio, battery_cycles_year1.
- Create a new pydantic result model (e.g. BatteryFinanceResult) that extends or parallels FinanceResult.
- The existing PV-only path (run_pv_finance) MUST remain unchanged and all G3 tests MUST still pass.

Key interfaces already established (do NOT break these):
- ProductionResult (src/gesfeas/production/models.py): has hourly_production_kwh (8760 list).
- FinanceInput / FinanceResult / TariffConfig (src/gesfeas/finance/models.py): PV-only finance.
- SiteParameters (src/gesfeas/input/models.py): has shift_pattern, connection_type.
- config/tariffs/2026.yaml: current PV-only tariff config.

Testing:
- Golden-file test: pin PV+Storage outputs for a fixed reference case in tests/golden/g4_reference.json.
- Shift-pattern test: run the same system with single-shift vs triple-shift load profiles. Assert that self_consumption_ratio and NPV differ meaningfully — storage should add more value for single-shift (daytime load aligns with PV, less storage value) vs triple-shift (nighttime load benefits from storage).
- Config-driven test: changing battery CAPEX in config changes outputs with NO code change.
- Regression: all existing G3 tests MUST still pass.

Acceptance criteria:
- `pytest` is green (all tests, including existing G3 golden-file test).
- PV+Storage scenario produces a BatteryFinanceResult with all required metrics.
- Shift-pattern impact is observable and tested.
- Changing battery config changes outputs (proven by a test).
- No changes outside src/gesfeas/finance/, tests/, tests/golden/, config/tariffs/.

When acceptance criteria pass: update PROGRESS.md (mark G4 done), commit to `develop`, and STOP.
```

---

## G5 — Regulation Rule Engine (config-driven, YAML)

```
You are implementing GOAL G5 (Regulation rule engine) of the GES feasibility engine. Read AGENTS.md, PROJECT_BRIEF.md, and REGULATION_NOTES.md first. Do ONLY G5. Do not touch other modules.

Scope (in src/gesfeas/regulation/ and config/regulation/):
- Build a config-driven regulation rule engine that evaluates whether a proposed PV (or PV+Storage) installation is compliant with Turkish EPDK unlicensed generation rules.
- All regulatory limits and thresholds MUST live in YAML files under config/regulation/. Python code reads and applies rules; it NEVER contains hardcoded regulatory values. This is a HARD RULE from AGENTS.md.
- Create two regulation config branches:
  - config/regulation/rooftop.yaml — rules for roof-mounted (çatı) installations.
  - config/regulation/ground_mount.yaml — rules for ground-mounted (arazi) installations.

Regulation rules to implement (each as a named, testable rule):

1. **max_capacity_kw**: Unlicensed production capacity limit (currently 25 kW for rooftop under 5.1.j/5.1.ç; different limits may apply for ground-mount 5.1.h). Value comes from YAML.
2. **transformer_capacity_check**: System size must not exceed transformer capacity (kVA). Threshold ratio from YAML.
3. **self_consumption_ratio_min**: For self_consumption_limited connection type, minimum self-consumption ratio (if applicable). Value from YAML.
4. **netting_mode**: Specifies the netting/mahsuplaşma regime (monthly vs hourly). This affects finance calculations downstream (G6 will consume this). Store as enum in YAML.
5. **hybrid_storage_allowed**: Whether PV+Storage (hybrid) is allowed under current regulation for this mount type. Boolean from YAML.
6. **ground_mount_eligibility**: For ground-mount only — additional requirements (industrial/agricultural use, zoning status). Modeled as a checklist of boolean flags in YAML.

Module design:
- A pydantic model for RegulationConfig that loads from YAML (one model, parameterized by mount_type).
- A pydantic model for RegulationResult containing: is_compliant (bool), violations (list of rule names + descriptions), warnings (list of advisory notes).
- A function `evaluate_compliance(site: SiteParameters, system_size_kw: float, self_consumption_ratio: Optional[float], regulation_config: RegulationConfig) -> RegulationResult` that runs all applicable rules and returns the result.
- Populate REGULATION_NOTES.md with the actual rule descriptions and their YAML field mappings.

Testing:
- Unit test each rule independently: a compliant case passes, a violating case returns the correct violation.
- Test rooftop: 20 kW system → compliant; 30 kW system → violation on max_capacity_kw.
- Test ground-mount: different limits, ground_mount_eligibility flags.
- Config-driven proof: change max_capacity_kw in YAML from 25 to 50 → the 30 kW case now passes. No code change.
- Test that hybrid_storage_allowed=false produces a violation when PV+Storage is proposed.

Acceptance criteria:
- `pytest` is green.
- Regulation rules are 100% config-driven. Changing a YAML value changes compliance outcome (proven by test).
- Both rooftop and ground-mount regulation branches exist and are tested.
- REGULATION_NOTES.md is populated with rule descriptions.
- No changes outside src/gesfeas/regulation/, config/regulation/, tests/, REGULATION_NOTES.md.

When acceptance criteria pass: update PROGRESS.md (mark G5 done), commit to `develop`, and STOP.
```

---

## G6 — Scenario Comparison & Decision Logic

```
You are implementing GOAL G6 (Scenario comparison & decision logic) of the GES feasibility engine. Read AGENTS.md and PROJECT_BRIEF.md first. Do ONLY G6. Do not touch other modules' internal logic.

Scope (in src/gesfeas/scenario/):
- Build the orchestration layer that runs and compares two scenarios side-by-side:
  1. **PV-only** (using G3's run_pv_finance)
  2. **PV + Storage** (using G4's battery finance function)
- For each scenario, also run G5's regulation compliance check.
- Consume inputs from the upstream modules:
  - SiteParameters + parsed consumption (from input module)
  - ProductionResult with 8760 hourly series (from production module)
  - TariffConfig + battery config (from config/tariffs/)
  - RegulationConfig (from config/regulation/)

Output model (pydantic):
- ScenarioResult: contains pv_only: FinanceResult, pv_storage: BatteryFinanceResult, pv_only_compliance: RegulationResult, pv_storage_compliance: RegulationResult, recommendation: str, recommendation_rationale: str.
- The recommendation logic should consider: NPV difference, payback period, compliance status, and self_consumption_ratio. If PV+Storage is non-compliant (hybrid_storage_allowed=false), recommend PV-only regardless of financial superiority.

Key function:
- `compare_scenarios(site: SiteParameters, consumption_df: pd.DataFrame, production: ProductionResult, tariff_config: TariffConfig, battery_config: BatteryTariffConfig, regulation_config: RegulationConfig) -> ScenarioResult`

This module is the "glue" — it should import from finance, regulation, and input modules but NOT duplicate their logic. Keep it thin.

Testing:
- End-to-end integration test using fixture data: given a known site + production + consumption, the comparison produces both scenario results and a recommendation.
- Test that when hybrid storage is not allowed by regulation, the recommendation is PV-only even if PV+Storage has better NPV.
- Test that for a high self-consumption facility (triple shift), PV-only may be recommended over PV+Storage (marginal storage value).
- Test that for a single-shift facility with low self-consumption, PV+Storage is recommended.
- All upstream module tests (G1–G5) MUST still pass.

Acceptance criteria:
- `pytest` is green.
- ScenarioResult contains complete finance + compliance for both scenarios.
- Recommendation logic is tested for at least 3 distinct cases.
- No changes outside src/gesfeas/scenario/, tests/.

When acceptance criteria pass: update PROGRESS.md (mark G6 done), commit to `develop`, and STOP.
```

---

## G7 — Report Generator (Jinja2 → HTML → PDF)

```
You are implementing GOAL G7 (Report generator) of the GES feasibility engine. Read AGENTS.md and PROJECT_BRIEF.md first. Do ONLY G7. Do not touch other modules.

Prerequisites — install new dependencies:
- Add jinja2 and weasyprint to pyproject.toml dependencies. Run `uv sync` (or pip install) to install them.

Scope (in src/gesfeas/report/):
- Build a report generator that takes a ScenarioResult (from G6) plus site/input metadata and produces a professional feasibility report in HTML and PDF formats.
- Use Jinja2 templates stored under src/gesfeas/report/templates/.
- Use WeasyPrint to convert the rendered HTML to PDF.

Report content (sections):
1. **Cover page**: Project title, location, date, company logo placeholder.
2. **Executive Summary**: One-paragraph recommendation with key numbers (system size, CAPEX, payback, NPV).
3. **Site Information**: Location, area, mount type, transformer capacity, shift pattern.
4. **Consumption Profile**: Monthly consumption table/chart placeholder (the template should have a table; actual chart rendering is optional in MVP).
5. **Production Estimate**: Annual production, capacity factor, system size.
6. **Financial Analysis — PV Only**: CAPEX, annual savings, NPV, LCOE, simple payback, discounted payback.
7. **Financial Analysis — PV + Storage**: Same metrics + self_consumption_ratio, grid_export_ratio, battery_cycles.
8. **Scenario Comparison**: Side-by-side table of key metrics; highlight the recommended scenario.
9. **Regulatory Compliance**: Compliance status for each scenario; list any violations or warnings.
10. **Assumptions & Disclaimers**: Tariff source, discount rate, degradation, data vintage.

Module design:
- A function `generate_report_html(scenario_result: ScenarioResult, site: SiteParameters, consumption_df: pd.DataFrame, production: ProductionResult) -> str` that renders the Jinja2 template.
- A function `generate_report_pdf(html_content: str, output_path: str) -> str` that converts HTML to PDF via WeasyPrint and returns the output file path.
- A convenience function `generate_full_report(scenario_result, site, consumption_df, production, output_path) -> str` that does both.
- Template files: at least one main template (e.g., feasibility_report.html) with professional CSS styling inline or in a companion CSS file.

Testing:
- Unit test: render HTML from a fixture ScenarioResult; assert that key sections and values appear in the HTML string.
- PDF generation test: generate a PDF file; assert the file exists and has non-zero size. (Visual inspection is manual; the automated test checks generation succeeds.)
- Save a sample generated report (HTML) in tests/golden/g7_sample_report.html as a reference.
- All upstream tests MUST still pass.

Acceptance criteria:
- `pytest` is green.
- For fixture inputs, a complete HTML report is generated containing all 10 sections.
- PDF generation succeeds (file created with non-zero size).
- Template is in src/gesfeas/report/templates/, not hardcoded in Python.
- No changes outside src/gesfeas/report/, tests/, tests/golden/, pyproject.toml.

When acceptance criteria pass: update PROGRESS.md (mark G7 done), commit to `develop`, and STOP.
```

---

## G8 — UI (Streamlit MVP)

```
You are implementing GOAL G8 (Streamlit MVP UI) of the GES feasibility engine. Read AGENTS.md and PROJECT_BRIEF.md first. Do ONLY G8. Do not touch other modules' internal logic.

Prerequisites — install new dependency:
- Add streamlit to pyproject.toml dependencies. Run `uv sync` (or pip install).

Scope (create app/ directory at repo root for the Streamlit app):
- Build a Streamlit-based web interface that allows a user to:
  1. Upload a consumption CSV file.
  2. Enter site parameters via a form: latitude, longitude, available area (m²), transformer capacity (kVA), mount type (dropdown: rooftop/ground), shift pattern (dropdown), connection type (dropdown).
  3. Optionally specify system size (kWp) or let it be auto-estimated.
  4. Click "Run Feasibility Analysis" to trigger the full pipeline.
  5. View results on screen: key metrics, scenario comparison table, compliance status, recommendation.
  6. Download the generated PDF report.

Architecture:
- The Streamlit app imports and calls the existing modules (input, production, finance, regulation, scenario, report) — it is a thin UI layer, NOT a reimplementation.
- Create app/main.py as the Streamlit entry point (run with `streamlit run app/main.py`).
- Handle errors gracefully: if CSV is malformed, show a clear error message. If PVGIS fetch fails, show a warning and suggest retry.

UI layout:
- Sidebar: site parameter form + CSV upload.
- Main area: results display after analysis runs.
- Use Streamlit's st.columns, st.metric, st.dataframe, st.download_button for a clean layout.
- Show a spinner during computation (PVGIS fetch + PySAM + report generation can take time).

Testing:
- Since Streamlit apps are hard to unit test, focus on:
  1. A smoke test that imports app/main.py without errors.
  2. An integration test that programmatically calls the same pipeline the UI would call (input → production → finance → regulation → scenario → report) with fixture data and asserts the full pipeline succeeds end-to-end.
- All upstream tests MUST still pass.

Acceptance criteria:
- `pytest` is green.
- `streamlit run app/main.py` launches without errors (manually verified; the automated test checks import and pipeline).
- The end-to-end pipeline test passes: fixture CSV → production → finance (both scenarios) → regulation → comparison → report PDF generated.
- No changes outside app/, tests/, pyproject.toml.

When acceptance criteria pass: update PROGRESS.md (mark G8 done), commit to `develop`, and STOP.
```

---

## G9 — Validation & Regression Suite

```
You are implementing GOAL G9 (Validation & regression suite) of the GES feasibility engine. Read AGENTS.md and PROJECT_BRIEF.md first. Do ONLY G9. Do not touch module business logic.

Scope (in tests/ and tests/golden/):
- Build a comprehensive regression and validation test suite that catches any future drift in outputs across the full pipeline.
- This is NOT about adding new features — it is about locking down correctness and preventing regressions.

Tasks:

1. **Golden-file regression suite**:
   - Create a full end-to-end golden file: tests/golden/g9_full_pipeline.json that captures the complete ScenarioResult (PV-only + PV+Storage finance, compliance, recommendation) for a fixed reference case.
   - The reference case should use: the Ankara PVGIS fixture (already in tests/fixtures/), the sample consumption CSV, a defined SiteParameters, and the 2026.yaml tariff config.
   - Assert all numeric outputs match the golden file within tolerance. If any output drifts, the test fails — forcing explicit re-validation.

2. **Cross-module integration tests**:
   - Test the complete chain: parse CSV → run production (offline, with cached PVGIS) → run PV-only finance → run PV+Storage finance → run regulation check → run scenario comparison.
   - Assert type correctness at each stage boundary (each module's output is the correct pydantic model).
   - Assert no NaN/null values leak through the pipeline.

3. **Regulation config regression**:
   - Pin the current regulation YAML configs (rooftop.yaml, ground_mount.yaml) as golden snapshots.
   - A test reads the YAML and compares against the pinned snapshot — ensures regulation configs are not accidentally modified.

4. **Sensitivity / sanity checks**:
   - Doubling system size roughly doubles CAPEX (within tolerance).
   - A location with higher irradiance (e.g., Antalya vs Ankara, if a second fixture is available) produces more energy.
   - Zero consumption → all production is exported → self_consumption_ratio = 0.
   - Negative NPV scenario: set absurdly high CAPEX in a test config → assert NPV < 0 and payback = lifetime.

5. **Test organization**:
   - Create tests/test_regression.py for all golden-file tests.
   - Create tests/test_integration.py for cross-module integration.
   - Create tests/test_sanity.py for sensitivity / sanity checks.
   - Ensure all tests run offline (no network calls).

6. **DECISIONS.md update**:
   - Document that the G9 golden files establish the regression baseline.
   - Note that any intentional output change requires updating golden files AND documenting the reason in DECISIONS.md.

Acceptance criteria:
- `pytest` is green — ALL tests (G1–G9) pass.
- Golden files exist for: G3 (PV-only finance), G4 (PV+Storage finance), G9 (full pipeline).
- At least 3 sanity/sensitivity checks pass.
- Cross-module integration test covers the full pipeline.
- DECISIONS.md documents the regression baseline policy.
- No changes to module business logic (src/gesfeas/**/*.py). Only tests/, tests/golden/, tests/fixtures/, and DECISIONS.md may be modified.

When acceptance criteria pass: update PROGRESS.md (mark G9 done), commit to `develop`, and STOP.
```

---

## Kullanım Notları

| # | Prompt'u vermeden önce | Neden |
|---|---|---|
| 1 | `AGENTS.md` ve `PROJECT_BRIEF.md`'yi context'e alın | Her goal bu dosyaları okuyor; priming hızı artar |
| 2 | Sadece ilgili modül dosyalarını context'e alın, tamamını değil | Token tasarrufu |
| 3 | İlgili kütüphane doküman linkini verin (pvlib, PySAM, WeasyPrint, Streamlit) | Daha doğru implementasyon |
| 4 | Goal'leri sırayla çalıştırın; önceki goal'ün testleri geçiyor olmalı | Bağımlılık zinciri: G4→G5→G6→G7→G8→G9 |
| 5 | Her goal sonunda `pytest` çalıştırıp yeşil olduğunu doğrulayın | Regresyon güvenliği |
