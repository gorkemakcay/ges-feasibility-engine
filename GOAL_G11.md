# Goal G11 — TRY Currency + Netting Wiring + Time-of-Use Tariff

> Full specification for autonomous goal G11. The `/goal` condition is a thin pointer to this file.
> Read AGENTS.md, PROJECT_BRIEF.md, and DECISIONS.md (G10 entry) first. Daima Türkçe konuş.

## Objective
Make the tariff/finance layer reflect Turkish market reality: prices in **TRY**, **time-of-use (TOU)**
energy rates, and the regulatory **netting regime (saatlik vs aylık mahsuplaşma)** actually driving the
finance. Build on G10's PySAM `Utilityrate5` + `Cashloan` chain — do not rewrite it.

## Key facts (trust, don't re-derive)
- Finance runs through `src/gesfeas/finance/pysam_rollup.py` (`Utilityrate5` + `Cashloan`).
- `Utilityrate5` already supports TOU via `ur_ec_tou_mat` + `ur_ec_sched_weekday/weekend` (12×24 period
  matrices). The engine just doesn't expose it yet — it uses a single FLAT period.
- `netting_mode` maps to `ur_metering_option` (hourly = net billing = 2 = saatlik; monthly = net metering
  = 0 = aylık) in `NETTING_TO_METERING`, BUT `scenario/engine.py` never passes it into the finance calls,
  so the regulatory regime is currently a **no-op** in finance (default "hourly" is always used).
- Currency is USD, a single FLAT buy $0.12 / sell $0.08 per kWh, and "$" is hardcoded in `app/main.py`
  (dashboard table + assumptions expander) and in `report/generator.py` + the Jinja2 template.

## Part A — Time-of-use (TOU) tariff (config-driven, no hardcoded rates)
- Extend `TariffConfig` to support a TOU energy-rate structure alongside the existing flat buy/sell (keep
  the flat path as fallback / default so nothing breaks).
- Model Turkey's 3 zones: **gece / gündüz / puant**, each with an hour-of-day range and a buy rate (and a
  sell/export rate).
- In `pysam_rollup`, when a TOU structure is present, build `ur_ec_tou_mat` (one row per period) and
  `ur_ec_sched_weekday/weekend` (12×24 period assignment) from it instead of the single flat period. The
  flat path stays as-is.
- Add a realistic TRY TOU tariff config (e.g. `config/tariffs/2026_try.yaml`). Use clearly-labelled
  **placeholder** rates the user can adjust; do NOT invent authoritative figures.

## Part B — Wire the netting regime through (saatlik mahsuplaşma)
- `scenario/engine.py` must read `regulation_config.netting_mode` and pass it into `run_pv_finance` and
  `run_pv_storage_finance`, so the regulatory regime actually drives the bill valuation.
- Keep the finance functions' default at `"hourly"`.

## Part C — Currency = TRY end-to-end
- Add a `currency` field to `TariffConfig` (default `"TRY"`). Thread it additively into
  `FinanceResult`/`BatteryFinanceResult` (or expose via the tariff) so display layers can read it.
- Replace hardcoded `"$"` in `app/main.py` (dashboard table + assumptions expander) and in
  `report/generator.py` + the Jinja2 template with the configured currency symbol/label.
- Set realistic TRY macro assumptions in the TRY config: TL inflation, discount, and loan rates are much
  higher than USD — make them config values, clearly documented as assumptions to be validated, NOT
  hardcoded in Python. Note in DECISIONS.md that Turkish solar feasibility is often modelled in USD to
  avoid TL volatility; TRY mode is offered but its macro rates must be user-confirmed.

## Testing
- **TOU test:** a period-heavy load (more consumption in puant hours) yields a different (higher) bill than
  the same energy under a flat rate; TOU vs flat produce different `annual_savings`.
- **Netting-wiring test:** running `compare_scenarios` with a regulation config `netting_mode="monthly"`
  vs `"hourly"` yields different finance outputs (proves the scenario now threads it; must fail if the
  scenario ignores `netting_mode`).
- **Currency test:** currency is present in results and changing it in config changes the displayed
  currency (no code change).
- Regenerate the affected goldens (`g3`/`g4`/`g9` stay USD/flat if you keep `2026.yaml` unchanged; add
  NEW goldens for the TRY/TOU config rather than breaking existing ones where possible). Any intentional
  golden change must be documented in DECISIONS.md.
- ALL existing tests must still pass; the scenario → report → PDF pipeline must run end-to-end.

## Constraints
- Config-driven: no hardcoded rates/currency in Python. TOU and flat both supported.
- No silent fallback in the PySAM path (keep G10's raise-on-failure).
- Keep public function signatures backward-compatible (additive params/fields only); the existing
  flat-USD path and its goldens must keep working unless you deliberately migrate them (and document it).

## Allowed paths
`src/gesfeas/finance/`, `src/gesfeas/scenario/`, `src/gesfeas/report/`, `config/tariffs/`,
`config/regulation/`, `app/main.py`, `tests/`, `tests/golden/`, `DECISIONS.md`, `VALIDATION.md`,
`PROGRESS.md`.

## Done
When ALL acceptance criteria pass (pytest green; TOU config-driven and flowing through Utilityrate5;
netting_mode threaded scenario→finance and tested; currency=TRY end-to-end in engine + config + UI +
report; goldens handled and documented), update PROGRESS.md (`[x] G11`) and commit to a feature branch.
Do NOT push to main unless the user explicitly authorises it.
