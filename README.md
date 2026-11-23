# A Multi-Tier Agri-Ecological Optimization Framework with Adaptive State-Dependent Orchestration and Nature-Boundary Gatekeeping

**Author:** Osama Ahmed Mohamed Gharib Mohamed Alwaly  
**Status:** preprint — manuscript and all reproduction artefacts are public in this repository.

This repository contains the manuscript, the executable benchmark that produces its
results, all figures, and the per-seed data. The framework defines three strictness
tiers ($\tau \in \{0,1,2\}$), positive-part-clipped sustainability indices, a monotone
stress-penalty map, a time-indexed nature gate, and a deterministic drought-triage rule.
The benchmark evaluates them against **two** conventional baselines (fixed-rate and
ET-scheduled irrigation) over a 52-week, 20-seed simulation.

## Repository layout

```
multi_tier_agri_ecological_optimization_framework.tex   manuscript (self-contained bibliography)
scripts/
  simulate_benchmark.py     5 policies x 20 seeds; writes all results tables and figs 3-6
  generate_figures.py       figs 1-2 (analytic schematics)
  verify_manuscript.py      structural checks; no TeX engine needed
results/
  results.json              100 per-seed records + summaries, paired stats, sensitivity
  results_table.tex         generated LaTeX headline table (\input by manuscript)
  stats_table.tex           generated paired-difference table
  diagnostics_table.tex     generated within-tier objective table
  sensitivity_table.tex     generated one-at-a-time sensitivity table
figures/                    all six PNGs referenced by the manuscript
data/references/
  extracted_sources.md      Zotero export of literature notes
LICENSE                     MIT
```

## Reproduce everything

Requires Python 3.10+, NumPy, SciPy and Matplotlib. From the repository root:

```sh
python scripts/simulate_benchmark.py
python scripts/generate_figures.py
python scripts/verify_manuscript.py
```

Both generators are fully deterministic: seeds are 100–119 and every stochastic draw
uses `numpy.random.default_rng(seed)`. Re-running them reproduces the committed results,
tables and figures byte-for-byte.

To build the PDF, use XeLaTeX or LuaLaTeX (`fontspec` and Noto Sans are required;
`pdflatex` will not work). This was verified with Tectonic 0.17.0:

```sh
xelatex multi_tier_agri_ecological_optimization_framework.tex
xelatex multi_tier_agri_ecological_optimization_framework.tex
```

## Empirical benchmark (mean ± SD over 20 seeds)

| Metric | Conv-Fixed | Conv-ET | AI-Low | AI-Med | AI-Strict |
|---|---|---|---|---|---|
| Yield (t/ha) | 5.76 ± 0.07 | **6.41 ± 0.04** | **6.41 ± 0.04** | 5.81 ± 0.03 | 5.49 ± 0.03 |
| Irrigation (m³/ha) | 8580 | 5383 ± 381 | 5383 ± 381 | 5383 ± 381 | 5437 ± 388 |
| IoT energy (kWh/ha) | 131.0 | 131.0 | 17.5 ± 0.6 | 17.5 ± 0.6 | **16.7 ± 0.5** |
| ΔSOC (g/kg) | −0.18 | −0.18 | −0.18 | +0.99 | **+1.69** |
| Crop-loss crop-weeks | 8.90 | 4.90 | 4.90 | 4.90 | **4.40** |

The headline attribution matters:

- ET-scheduled irrigation, not the AI tier, produces the entire **−37% water** and
  **+11% yield** gain over fixed-rate scheduling; `AI-Low` is identical to `Conv-ET`
  on both metrics.
- Adaptive duty cycling (polling rises with telemetry demand $\beta$) produces the
  **−87% IoT energy** saving, with no further water or yield cost.
- The strictness ladder is a genuine trade-off: ΔSOC rises and yield falls as
  strictness increases; `AI-Strict` has the fewest crop-loss events.

Paired $t$ tests on the 20 shared seeds (95% CIs) and a $\pm25\%$ one-at-a-time
sensitivity check over all ten response coefficients are in `results.json` and the
generated tables; all four encoded robustness checks survive every perturbation.
$\mathcal{J}$ is a within-tier diagnostic because tier-specific weights and the
nature gate suppress it by construction; it is not a cross-policy ranking score.

**Scope:** these are simulation results from parsimonious response functions, not a
multi-season field trial. Coefficient magnitudes are illustrative; the orderings are
the transferable claim. Lysimeter and sensor-testbed calibration is still required.

## Verification performed

- All 12 DOI records resolve via OpenAlex (2 re-checked via Semantic Scholar during an
  OpenAlex rate limit); none reported retracted.
- 12 cites / 12 bibitems; refs/labels, braces and environments checked by
  `verify_manuscript.py`; all six figure files and four generated tables present.
- Peak simultaneous evapotranspiration is 314.4 m³/week, below the 600 m³/week supply cap.
- The corrected duty law is reproduced directly from `simulate_benchmark.py`:
  $\beta=1 \to M_{\mathrm{duty}}=0.05$, $\beta=5 \to M_{\mathrm{duty}}=0.40$.
- The 17-page PDF compiles with Tectonic 0.17.0 (XeTeX engine): no LaTeX errors,
  no undefined references, all four generated tables and all six figures present.
  A harmless `fontspec` language warning for Noto Sans is emitted by Tectonic.

## Licence

MIT — see [LICENSE](LICENSE).
