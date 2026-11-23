# A Multi-Tier Agri-Ecological Optimization Framework with Adaptive State-Dependent Orchestration and Nature-Boundary Gatekeeping

**Author:** Osama AlWaly  
**Status:** preprint — manuscript and all reproduction artefacts are public in this repository.

This repository contains the manuscript, the executable benchmark that produces its
results, all figures, and the per-seed data. The framework defines three strictness
tiers ($\tau \in \{0,1,2\}$), positive-part-clipped sustainability indices, a monotone
water-penalty map, a time-indexed nature gate, and a deterministic drought-triage rule,
and evaluates them against a conventional baseline over a 52-week, 20-seed simulation.

## Repository layout

```
multi_tier_agri_ecological_optimization_framework.tex   manuscript (self-contained bibliography)
scripts/
  simulate_benchmark.py     4 policies x 20 seeds; writes results/ and figs 3-5
  generate_figures.py       figs 1-2 (analytic schematics)
  verify_manuscript.py      structural checks; no TeX engine needed
results/
  results.json              all 80 per-seed records + summary statistics
  results_table.tex         generated LaTeX table (embedded in the manuscript)
figures/                    all five PNGs referenced by the manuscript
data/references/
  extracted_sources.md      Zotero export of literature notes
LICENSE                     MIT
```

## Reproduce everything

Requires Python 3.10+, NumPy and Matplotlib. From the repository root:

```sh
python scripts/simulate_benchmark.py
python scripts/generate_figures.py
python scripts/verify_manuscript.py
```

Both generators are fully deterministic: seeds are 100–119 and every stochastic draw
uses `numpy.random.default_rng(seed)`. Re-running them reproduces the committed results
and figures byte-for-byte.

To build the PDF, use XeLaTeX or LuaLaTeX (`fontspec`, `bidi=basic` and Noto Sans are
required; `pdflatex` will not work):

```sh
xelatex multi_tier_agri_ecological_optimization_framework.tex
xelatex multi_tier_agri_ecological_optimization_framework.tex
```

## Empirical benchmark (mean ± SD over 20 seeds)

| Metric | Conventional | AI-Low | AI-Med | AI-Strict |
|---|---|---|---|---|
| Yield (t/ha) | 5.76 ± 0.07 | **6.41 ± 0.04** | 5.81 ± 0.03 | 5.49 ± 0.03 |
| Irrigation (m³/ha) | 8580 | 5384 ± 381 | 5384 ± 381 | 5438 ± 388 |
| IoT energy (kWh/ha) | 131.0 | 32.3 ± 0.9 | 32.3 ± 0.9 | **29.5 ± 0.7** |
| ΔSOC (g/kg) | −0.18 | −0.18 | +0.99 | **+1.69** |
| Crop-loss crop-weeks | 8.90 | 4.90 | 4.90 | **4.40** |

State-dependent allocation cuts irrigation by ~37% and IoT energy by over 75% while
AI-Low still raises yield by 11%. The strictness ladder is a genuine trade-off: soil
carbon rises and yield falls as strictness increases. AI-Strict has the fewest
crop-loss events. Rankings are unchanged when the 20 seeds are split into two disjoint
halves. $J$ is a within-tier diagnostic because AI-Strict's nature gate is zero during
triage; it is not a cross-policy ranking score.

**Scope:** these are simulation results from parsimonious response functions, not a
multi-season field trial. Coefficients are not sensitivity-tested and require
lysimeter / sensor-testbed calibration before agronomic claims are made.

## Verification performed

- All 12 DOI records resolve via OpenAlex; none retracted; metadata cross-checked with Crossref.
- 12 cites / 12 bibitems; 17 refs / 17 labels; balanced braces and environments.
- Peak simultaneous evapotranspiration is 314.4 m³/week, below the 600 m³/week supply cap.
- The manuscript was not compiled here because no XeLaTeX/LuaLaTeX engine is installed.

## Licence

MIT — see [LICENSE](LICENSE).
