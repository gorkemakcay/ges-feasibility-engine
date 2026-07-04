# DECISIONS.md

- **Language:** Python 3.11+ will be the single language for the entire backend to unify pvlib and PySAM.
- **Regulation Rules:** Stored as external configuration (YAML/JSON), completely separated from code logic. This makes adapting to changing Turkish EPDK regulations easier.
- **Scope Boundary:** We are NOT building a 3D CAD/layout tool. We leave layout to tools like PVCase and focus on financial modeling, regulation compliance, and feasibility reporting.
- **Architecture:** Autonomous goals run linearly on the `develop` branch.
- **Libraries:** We rely on established open-source engines (`pvlib`, `nrel-pysam`) instead of building custom mathematical models for solar and financial simulations.
- **Finance Engine Validation:** The golden baseline used for testing the PV-only PySAM financial model must be validated against a manual SAM GUI run before production use. The current golden test catches regressions, but not necessarily correctness relative to SAM GUI output.
