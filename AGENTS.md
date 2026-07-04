# AGENTS.md

## Purpose
This project is an autonomous feasibility engine for solar (GES) investments in Turkey. It calculates technical production, financial viability, and regulatory compliance for both roof-mounted and ground-mounted solar scenarios, with or without storage.

## Architecture
- **Input:** Consumption data (CSV), site parameters, location.
- **Production Engine:** pvlib (radiation -> generation via PVGIS).
- **Finance + Battery Engine:** PySAM / SAM (CAPEX, NPV, LCOE, battery dispatch).
- **Regulation Engine:** Config-driven rules (YAML) based on EPDK regulations.
- **Scenario Comparison:** Compares PV-only vs. PV+Storage.
- **Report Generator:** Jinja2 -> HTML -> PDF (via WeasyPrint).

## Tech Stack
- **Language:** Python 3.11+
- **Production:** pvlib
- **Finance:** nrel-pysam
- **Configuration/Regulation:** PyYAML / pydantic
- **Testing:** pytest

## Goals (G0-G9)
- **G0:** Skeleton & CI setup (Current)
- **G1:** Input parsing module
- **G2:** Production engine (pvlib integration)
- **G3:** Finance engine (PySAM integration)
- **G4:** Battery scenario (PySAM)
- **G5:** Regulation rule engine (config-driven)
- **G6:** Scenario comparison & logic
- **G7:** Report generator
- **G8:** UI (Streamlit MVP)
- **G9:** Validation & regression suite

## HARD RULES
1. **Regulation is config-driven:** Never hardcoded in Python. Use YAML files for regulatory limits.
2. **No 3D/CAD:** Do NOT rebuild PVCase's CAD/3D engine. Scope is strictly finance + regulation + report.
3. **Isolation:** Every goal is isolated, has clear acceptance criteria + tests, and must update `PROGRESS.md` when done.
4. **Use validated libraries:** Prefer pvlib and PySAM over custom math.
