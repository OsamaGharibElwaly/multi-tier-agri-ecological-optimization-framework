# A Multi-Tier Agri-Ecological Optimization Framework with Adaptive State-Dependent Orchestration and Nature-Boundary Gatekeeping

[![Status](https://img.shields.io/badge/Manuscript-Revision%20In%20Progress-1d4ed8.svg)](#manuscript-status--future-citation)
[![Tiers](https://img.shields.io/badge/Strictness%20Tiers-%5Ctau%20%5Cin%20%5C%7B0%2C1%2C2%5C%7D-047857.svg)](#methodology-summary)
[![Horizon](https://img.shields.io/badge/Simulation-52%20Weeks%20(%20K%3D3%20Crops%20)-0f766e.svg)](#experimental-setup--stress-test)
[![Drought Test](https://img.shields.io/badge/Drought%20Window-Weeks%2024--29-b45309.svg)](#experimental-setup--stress-test)
[![License](https://img.shields.io/badge/License-MIT-374151.svg)](#license)

Companion codebase, simulation notebook, figure generators, and reference materials for **"A Multi-Tier Agri-Ecological Optimization Framework with Adaptive State-Dependent Orchestration and Nature-Boundary Gatekeeping"** by **Osama Ahmed Mohamed Gharib Mohamed Alwaly** (Department of Computer Engineering, Port Said University, Egypt).

## Manuscript Status & Future Citation

> **Note:** `paper_revised_2.tex` is withheld for now and will be added in a future update once all final review considerations, multi-seed runs, and experimental outcomes are complete. Full citation support (`CITATION.cff` and BibTeX) will be added alongside the finalized paper so it can be cited directly. Until then, cite only this repository when referencing the code or figures.

## Methodology Summary

Evaluates a 52-week coupled agri-ecological model across soil quality ($S$), crop performance ($C$ across $K=3$ crop groups: winter wheat, grain maize, and legume cover crop), IoT monitoring ($M$ with $\beta_{\AAI} \in [1.0, 5.0]$ and floor $M_{\min}$), water balance ($W$ with $\omega_t$, $\phi_{\AAI} \in [1.0, 5.0]$, and root-zone floor $W_{\mathrm{crit},k}$), and supplier/infrastructure context ($\mathrm{Sup}$). Compares `Conventional`, `AI-Low` ($\tau=0$), `AI-Med` ($\tau=1$), and `AI-Strict` ($\tau=2$, non-compensatory clipped multiplicative soil-crop core, squared depletion penalties, $C_{\mathrm{chem}}=0$, nature gate $\mathbb{I}_{\mathrm{nat}}^{(2)}$, and drought fallback), including a six-week summer drought stress test (**Weeks 24–29**). Physical metrics (yield in $\mathrm{t/ha}$, water in $\mathrm{m}^3$, sensor energy in $\mathrm{kWh}$, and $\Delta\mathrm{SOC}$ in $\mathrm{g/kg}$) anchor cross-system comparisons, while $\mathcal{J}_{\tau}$ serves as a within-tier diagnostic.

## Repository Structure

- `notebooks/agentic_ai_agro_ecological_optimization.ipynb` — Simulation and optimization notebook
- `scripts/generate_figures.py` (and root `generate_figures.py`) — Figure generation script
- `figures/` (and root `*.png` figures) — Architecture, tier progression, synergy contour, drought stress-test, and radar comparison figures
- `results/` — Aggregated simulation outputs and tables (populated as runs complete)
- `data/references/` (and root `references.bib`) — Reference PDFs, `extracted_sources.md`, and BibTeX entries

## Roadmap

- [ ] Run multi-seed ($N \ge 20$) experiments and populate `mean ± SD` physical outcome tables in `results/`.
- [ ] Add `paper_revised_2.tex` after final review considerations and outcomes.
- [ ] Add `CITATION.cff` and BibTeX citation block once ready to cite.

## License

MIT License
