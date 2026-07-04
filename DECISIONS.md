# DECISIONS.md

- **Language:** Python 3.11+ will be the single language for the entire backend to unify pvlib and PySAM.
- **Regulation Rules:** Stored as external configuration (YAML/JSON), completely separated from code logic. This makes adapting to changing Turkish EPDK regulations easier.
- **Scope Boundary:** We are NOT building a 3D CAD/layout tool. We leave layout to tools like PVCase and focus on financial modeling, regulation compliance, and feasibility reporting.
- **Architecture:** Autonomous goals run linearly on the `develop` branch.
- **Libraries:** We rely on established open-source engines (`pvlib`, `nrel-pysam`) instead of building custom mathematical models for solar and financial simulations.
- **Finance Engine Validation:** The golden baseline used for testing the PV-only PySAM financial model must be validated against a manual SAM GUI run before production use. The current golden test catches regressions, but not necessarily correctness relative to SAM GUI output.
- **Regression Baseline:** The G9 golden files (`g9_full_pipeline.json`, etc.) establish the regression baseline for the entire pipeline. Any intentional output change in the future requires updating these golden files AND documenting the reason for the change in this DECISIONS.md file.
- **G10 — Finance PySAM Migration:** The financial rollup (NPV, payback, LCOE) was migrated from hand-rolled Python cash-flow math to `PySAM.Utilityrate5` + `PySAM.Cashloan` (the same engine as the SAM desktop GUI). Consequences:
  - **Debt is now live.** `debt_fraction`, `loan_term`, and `loan_rate` (previously defined in `TariffConfig` but unused — NPV was effectively all-equity) now flow into `Cashloan` and move NPV. Proven by `test_debt_params_affect_npv`.
  - **Battery value flows through the financials.** `run_pv_storage_finance` keeps the hand-rolled hourly dispatch (`_run_dispatch`) but now feeds the post-dispatch metered output (`effective_gen = PV − charge + discharge`) alongside the REAL load into Utilityrate5, so storage value is captured in the bill savings. Proven by `test_battery_value_flows_through`.
  - **PV degradation is config-driven.** The previously hardcoded 0.5 %/yr moved to `TariffConfig.pv_degradation_rate` (`config/tariffs/2026.yaml`).
  - **Netting regime maps to metering option.** `netting_mode="hourly"` → net billing (per-timestep); `"monthly"` → net metering (monthly rollover / mahsuplaşma). Note: monthly net metering is `>=` hourly net billing in value for a self-consuming site (daytime exports offset nighttime imports at the retail buy rate) — the physically correct direction. See `test_netting_mode_affects_savings`.
  - **Goldens regenerated.** `g3_reference.json`, `g4_reference.json`, and `g9_full_pipeline.json` were regenerated from the new PySAM outputs (e.g. G3 NPV 129,298 → 137,200 due to live debt). Regeneration recipe: `scratch/regen_goldens_g10.py`.
  - **SAM sign-off pending.** A one-time human input-mapping cross-check against the SAM GUI is tracked in `VALIDATION.md` and is still pending. PySAM outputs are SAM outputs by construction; the sign-off only confirms input mapping.
