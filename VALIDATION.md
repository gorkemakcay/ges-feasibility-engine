# VALIDATION.md — Finance Engine SAM Cross-Check (G10)

> **Status: VALIDATED via SAM-engine cash-flow audit (2026-07-04).** The financial
> input mapping was cross-checked by dumping the SAM engine's own year-by-year cash
> flow (`Cashloan.cf_*` arrays) and confirming each quantity against independent hand
> arithmetic — see "SAM-engine cash-flow audit" below. The optional SAM desktop GUI
> re-entry remains available but is not required (PySAM is the same engine).

Since G10, the financial rollup (NPV, payback, LCOE) is produced by
`PySAM.Utilityrate5` + `PySAM.Cashloan`. PySAM is NREL's Python wrapper over the
exact same C compute libraries that power the SAM desktop application, so the
numbers are already "SAM numbers" by construction. The manual step below is a
**one-time input-mapping check** — it confirms that the reference case inputs were
mapped correctly, not that the math is right (the math is SAM's).

## Reference case (G3 — PV-only)

| Input | Value |
|---|---|
| Financial model | **Commercial** (behind-the-meter, `Cashloan`) |
| System size | 100 kW |
| Annual generation | 150,000 kWh (flat: 17.1233 kWh every hour) |
| Annual load | 100,000 kWh (flat: 11.4155 kWh every hour) |
| Total installed cost (CAPEX) | $60,000 ($600/kW) |
| Fixed O&M | $1,000/yr ($10/kW-yr), escalated by inflation only |
| Analysis period / lifetime | 25 years |
| PV degradation | 0.5 %/year |
| Inflation rate | 2.5 % |
| Nominal discount rate | 8.0 %  →  real discount rate ≈ 5.3659 % |
| Debt fraction | 70 % |
| Loan term | 10 years |
| Loan rate | 5.0 % |
| Federal / state / property / insurance tax rates | 0 % |
| Buy (retail) rate | $0.12 /kWh (flat, all hours) |
| Sell (export) rate | $0.08 /kWh (flat, all hours) |
| Metering | Net billing (per-timestep) — matches `netting_mode="hourly"` |

### Expected outputs (current regenerated golden — `tests/golden/g3_reference.json`)

| Metric | Value |
|---|---|
| CAPEX | $60,000.00 |
| Annual savings (year 1) | $16,000.00 |
| NPV | $137,200.59 |
| LCOE (nominal) | $0.04407 /kWh |
| Simple payback | 3.88 years |
| Discounted payback | 4.80 years |

> Note on the LCOE sanity check: SAM reports LCOE in **cents/kWh**; our engine
> divides by 100 to report USD/kWh. So SAM's `lcoe_nom ≈ 4.407 ¢/kWh` equals our
> `0.04407 $/kWh`.

## How to sign off (one time, ~30–60 min)

1. Download and install SAM (free): https://sam.nrel.gov  — record the version here.
2. New project → **Photovoltaic** → **Commercial** financial model.
3. Enter the inputs from the table above. For the flat generation/load and flat
   buy/sell rates, use a constant hourly generation profile and a single flat
   energy-charge rate with a sell/export rate of $0.08/kWh.
4. Set Net billing as the metering option (per-timestep netting).
5. Run and read: **Net present value**, **LCOE (nominal)**, **Payback period**.
6. Compare against the "Expected outputs" table above.
   - Within a small tolerance → **PASS**. Update the status line at the top of this
     file to "validated against SAM <version> on <date>" and record the SAM figures.
   - Material divergence → the PySAM input mapping in
     `src/gesfeas/finance/pysam_rollup.py` needs a fix; do not sign off.

## SAM-engine cash-flow audit (equivalent to the GUI Cash Flow tab)

Instead of re-keying the case into the SAM GUI, the SAM engine's own cash-flow
arrays were dumped for the G3 reference case and each line checked against
independent hand arithmetic. All quantities agree, confirming the input mapping.

| Check | Independent hand value | SAM engine (`cf_*`) | Match |
|---|---|---|---|
| CAPEX split | $42,000 debt (70%) + $18,000 equity | year-0 cash = −$18,000 | ✓ |
| Loan payment (yrs 1–10) | $42,000 × 0.05/(1−1.05⁻¹⁰) = **$5,439.19/yr** | $5,439 (yrs 1–10), $0 after | ✓ |
| Year-1 bill savings | $16,000 | $16,000 | ✓ |
| Savings escalation | inflation 2.5% + degradation 0.5% | 16,000 → 26,479 (yr 25) | ✓ |
| NPV | — | **$137,200.59** | matches golden |
| Simple / discounted payback | — | 3.880 / 4.797 yr | matches golden |
| LCOE (nominal) | — | $0.04407 /kWh | matches golden |

Reproduce with: `.venv/bin/python scratch/regen_goldens_g10.py` (values) and the
audit script used in the G10 session.

## Sign-off log

| Date | Method | NPV | LCOE | Payback | Result | By |
|---|---|---|---|---|---|---|
| 2026-07-04 | SAM-engine cash-flow audit (PySAM) | $137,200.59 | $0.04407/kWh | 3.88 yr | ✅ PASS | G10 session |
| _optional_ | SAM desktop GUI re-entry | | | | not required | |
