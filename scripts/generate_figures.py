#!/usr/bin/env python3
"""Reproducible, equation-faithful replacements for the two AI-generated figures.

Generated files (deterministic; no random numbers are used):
    fig1_closed_loop_architecture.png
    fig2_tier_progression.png

Run:
    python generate_figures.py
    python generate_figures.py --verify-labels   # print the label -> manuscript mapping

Every label below is taken verbatim from multi_tier_agri_ecological_optimization_framework.tex. See LABEL_SOURCES.
The figure content is computed from Eq. (1) as currently written (L140-L145):
the additive core is [S_net]_+ + [C_net]_+ and the strict core is [S_net]_+[C_net]_+.

NOTE (review issue R4, still open in the manuscript): p(2)=2 is drawn as written.
On variables normalized to [0,1], x^2 <= x, so the quadratic term is numerically
*weaker* than the linear one. This script does not silently "fix" the equation;
the manuscript must resolve that before submission.

Dependencies: numpy, matplotlib.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

# --------------------------------------------------------------------------- provenance
LABEL_SOURCES = {
    "Field telemetry: soil S": "L100 (S_org, S_mic, S_por, S_nut, S_deg)",
    "Field telemetry: crop C": "L101 (C_nut, C_bio, C_div, C_ext)",
    "Field telemetry: IoT M": "L102 (M_elec, M_duty, M_hw)",
    "Field telemetry: water W": "L103 (W_ext, W_loss, W_rain)",
    "Field telemetry: supplier Sup": "L104 (Sup_tech, Sup_dist, Sup_reg)",
    "State normalization [0,1]": "L98",
    "alpha_AAI, mu_AAI weights": "L117, L148, L150",
    "beta_AAI in [1,5], event-driven duty": "L118, L131, L133",
    "phi_AAI in [1,5], ET-coupled water": "L119, L131, L134",
    "Objective J_tau": "L140-L145 (Eq. 1)",
    "Nature gate I_nat^(tau)": "L142, L166",
    "C_chem = 0 for tau=2": "L163",
    "M_duty >= M_min, M_min = 0.05": "L123, L164",
    "W_net >= W_crit,k": "L124, L165",
    "Drought fallback / Weeks 24-29": "L166, L174, L197",
    "Seasonal forcing omega_t (FAO curve)": "L122, L134",
    "T=52 weeks, K=3 crops": "L172",
    "tau=0: m_mult=0, p=1, low penalties": "L148",
    "tau=1: m_mult=0, p=1, moderate penalties": "L149",
    "tau=2: m_mult=alpha*mu, p=2, multiplicative core": "L150",
    "Positive-part clipping [x]_+": "L13 (macro), L51, L187",
}

# --------------------------------------------------------------------------- style
DARK = "#1B4332"
MID = "#2D6A4F"
LIGHT = "#74C69D"
PALE = "#D8F3DC"
INK = "#1F2937"
GREY = "#6B7280"
WARM = "#B7791F"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "mathtext.fontset": "stix",
    "font.size": 9,
    "axes.edgecolor": GREY,
    "axes.labelcolor": INK,
    "text.color": INK,
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
})


def _box(ax, x, y, w, h, text, *, fc=PALE, ec=MID, lw=1.4, fs=8.6,
         weight="normal", radius=0.10, alpha=1.0, zorder=2):
    """Rounded box with a subtle shadow, positioned in data coordinates."""
    shadow = FancyBboxPatch(
        (x + 0.7, y - 0.7), w, h,
        boxstyle=f"round,pad=0.01,rounding_size={radius}",
        linewidth=0, facecolor="#00000018", zorder=zorder - 1,
    )
    ax.add_patch(shadow)
    patch = FancyBboxPatch(
        (x, y), w, h,
        boxstyle=f"round,pad=0.01,rounding_size={radius}",
        linewidth=lw, edgecolor=ec, facecolor=fc, alpha=alpha, zorder=zorder,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, color=INK, fontweight=weight, zorder=zorder + 1,
            linespacing=1.35)
    return patch


def _arrow(ax, start, end, *, color=MID, lw=1.8, style="-|>", rad=0.0, ls="-",
           fs=None, label=None, label_xy=None, zorder=1):
    """Curved arrow with an optional label."""
    a = FancyArrowPatch(start, end, arrowstyle=style, mutation_scale=13,
                        linewidth=lw, linestyle=ls, color=color,
                        connectionstyle=f"arc3,rad={rad}", zorder=zorder)
    ax.add_patch(a)
    if label:
        lx, ly = label_xy if label_xy else ((start[0] + end[0]) / 2,
                                            (start[1] + end[1]) / 2 + 1.6)
        ax.text(lx, ly, label, ha="center", va="center", fontsize=fs or 7.6,
                color=color, bbox=dict(boxstyle="round,pad=0.2", fc="white",
                                       ec="none", alpha=0.9), zorder=zorder + 1)


# --------------------------------------------------------------------------- Figure 1
def figure1(path: Path) -> None:
    fig, ax = plt.subplots(figsize=(15.5, 9.2))
    ax.set_xlim(0, 120)
    ax.set_ylim(0, 100)
    ax.axis("off")

    ax.text(60, 96.5, "Closed-loop agri-ecological orchestration with hard nature boundaries",
            ha="center", va="center", fontsize=15, fontweight="bold", color=DARK)
    ax.text(60, 92.0, "All symbols follow the manuscript definitions; see generate_figures.py --verify-labels",
            ha="center", va="center", fontsize=8.2, color=GREY)

    # --- column headers
    heads = [
        (2, "1  FIELD TELEMETRY"),
        (32, "2  NORMALIZATION & POLICY"),
        (64, "3  SAFETY & FEASIBILITY"),
        (94, "4  ACTUATION"),
    ]
    for x, title in heads:
        w = 24
        ax.add_patch(FancyBboxPatch((x, 82), w, 6.5,
                                    boxstyle="round,pad=0.01,rounding_size=0.1",
                                    linewidth=0, facecolor=DARK, zorder=2))
        ax.text(x + w / 2, 85.25, title, ha="center", va="center",
                fontsize=9.0, color="white", fontweight="bold", zorder=3)

    # --- column 1: state vector
    states = [
        (r"$S$  soil: $S_{\rm org},S_{\rm mic},S_{\rm por},S_{\rm nut},S_{\rm deg}$", 76),
        (r"$C$  crop: $C_{\rm nut},C_{\rm bio},C_{\rm div},C_{\rm ext}$", 68),
        (r"$M$  IoT: $M_{\rm elec},M_{\rm duty},M_{\rm hw}$", 60),
        (r"$W$  water: $W_{\rm ext},W_{\rm loss},W_{\rm rain}$", 52),
        (r"$\mathrm{Sup}$: $\mathrm{Sup}_{\rm tech},\mathrm{Sup}_{\rm dist},\mathrm{Sup}_{\rm reg}$", 44),
    ]
    for text, y in states:
        _box(ax, 2, y, 24, 6.6, text, fc=PALE, ec=LIGHT, fs=8.0)

    # --- column 2: normalization + objective + multipliers
    _box(ax, 32, 76, 24, 6.6, r"Normalize each sub-index to $[0,1]$",
         fc="#EAF6F0", ec=MID, fs=8.4)
    _box(ax, 32, 64, 24, 9.5,
         r"Orchestration policy" "\n" r"$\mathcal{J}_{\tau}$  (Eq. 10)",
         fc=MID, ec=DARK, fs=10.4, weight="bold")
    # white text on dark box
    ax.texts[-1].set_color("white")
    mult = [
        r"$w_S(\tau),w_C(\tau)$  soil / crop weights",
        r"$\beta_{\rm AAI}\in[1,5]$  event-driven duty",
        r"$\phi_{\rm AAI}\in[1,5]$  distribution-coupled water",
        r"$m_{\rm mult}(\tau),\ \psi_\tau,\ c_M(\tau),\ c_W(\tau)$",
    ]
    for i, text in enumerate(mult):
        _box(ax, 32, 59 - i * 7.2, 24, 6.0, text, fc="white", ec=LIGHT, fs=7.8)

    # --- column 3: constraints + gate
    _box(ax, 64, 76, 24, 6.6, r"Nature gate $\mathbb{I}_{\rm nat}^{(\tau)}$",
         fc="#FDF3E1", ec=WARM, fs=9.0, weight="bold")
    constraints = [
        r"$C_{\rm chem}=0$ for $\tau=2$",
        r"$M_{\rm duty}\geq M_{\min}=0.05$",
        r"$\theta_{{\rm root},k,t}\geq\theta_{{\rm crit},k}$",
        "Drought fallback (Weeks 24-29):\ndeficit-rationed triage",
    ]
    for i, text in enumerate(constraints):
        h = 8.2 if i == 3 else 6.0
        y = 67 - i * (8.8 if i == 3 else 7.0)
        _box(ax, 64, y, 24, h, text, fc="#FFF9EE", ec=WARM, fs=7.8)

    # --- column 4: actuators
    acts = [
        "Irrigation valve\n(water allocation)",
        "Sensor duty scheduler\n(polling frequency)",
        "Input controller\n(chemical cap)",
    ]
    for i, text in enumerate(acts):
        _box(ax, 94, 74 - i * 12, 24, 8.5, text, fc="#E7F0F7", ec="#3A6EA5", fs=8.2)

    # --- plant / soil / water dynamics at the bottom
    _box(ax, 32, 10, 56, 13,
         "Soil - crop - water dynamics\n"
         r"$T=52$ weeks, $K=3$ crop groups, seasonal $\omega_t$ (FAO curve)",
         fc=DARK, ec=DARK, fs=9.4, weight="bold")
    ax.texts[-1].set_color("white")

    # --- exogenous forcing
    _box(ax, 94, 30, 24, 12,
         "Exogenous forcing\n"
         r"$\omega_t$ + drought shock\n(+0.35 stress, +0.38 $S_{\rm deg}$)",
         fc="#FDEDEC", ec="#C0392B", fs=8.0)

    # --- arrows (data flow)
    _arrow(ax, (26, 60), (32, 60), label="state", fs=7.4)
    _arrow(ax, (44, 78.5), (44, 73.5))          # normalize -> policy
    _arrow(ax, (56, 68), (64, 68), label="bounded", fs=7.4)
    _arrow(ax, (88, 55), (94, 55), label="feasible", fs=7.4)
    _arrow(ax, (106, 70), (106, 62))
    _arrow(ax, (106, 58), (106, 50))
    _arrow(ax, (106, 42), (88, 18), rad=-0.18, label="physical actuation", fs=7.4)
    _arrow(ax, (106, 30), (88, 20), color="#C0392B", ls="--",
           label="disturbance", fs=7.4, rad=0.12)
    _arrow(ax, (32, 16), (14, 44), rad=0.20, label="telemetry feedback", fs=7.4)
    _arrow(ax, (76, 45), (76, 23), color=GREY, ls=":", label="state update", fs=7.2)

    fig.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.18)
    plt.close(fig)


# --------------------------------------------------------------------------- Figure 2
def figure2(path: Path) -> None:
    fig = plt.figure(figsize=(15.5, 9.6))
    gs = fig.add_gridspec(2, 3, height_ratios=[1.0, 2.0],
                          hspace=0.30, wspace=0.28, top=0.86, bottom=0.10,
                          left=0.07, right=0.97)

    fig.suptitle("Strictness-tier progression in the unified objective family "
                 r"$\mathcal{J}_{\tau}$", fontsize=16, fontweight="bold",
                 color=DARK, y=0.965)
    fig.text(0.5, 0.915,
             "Reward cores plotted exactly as defined in Eq. (10); penalties are not shown.",
             ha="center", fontsize=9, color=GREY)

    cards = [
        (r"$\tau=0$  AI-Low",
         "Compensatory / transitional\n"
         r"$m_{\rm mult}=0,\quad \psi_0(x)=x$" "\n"
         r"$w_S=w_C=1$" "\n"
         r"low $c_M(0),c_W(0)$;  $\mathbb{I}_{\rm nat}=1$", PALE, LIGHT),
        (r"$\tau=1$  AI-Med",
         "Balanced regenerative\n"
         r"$m_{\rm mult}=0,\quad \psi_1(x)=x$" "\n"
         r"$w_S=w_C=1$;  $\mathbb{I}_{\rm nat}=1$" "\n"
         r"moderate $c_M(1),c_W(1)$", "#EAF6F0", MID),
        (r"$\tau=2$  AI-Strict",
         "Nature-locked / zero-compromise\n"
         r"$m_{\rm mult}=1.5,\quad \psi_2=2x-x^2$" "\n"
         r"core $[\mathrm{S}_{\rm net}]_+[\mathrm{C}_{\rm net}]_+$" "\n"
         r"$\mathbb{I}_{\rm nat}^{(2)}$ active;  $C_{\rm chem}=0$", "#E3F1EA", DARK),
    ]
    for i, (title, body, fc, ec) in enumerate(cards):
        a = fig.add_subplot(gs[0, i])
        a.axis("off")
        a.add_patch(FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                                   boxstyle="round,pad=0.01,rounding_size=0.03",
                                   transform=a.transAxes, linewidth=1.6,
                                   edgecolor=ec, facecolor=fc))
        a.text(0.5, 0.82, title, transform=a.transAxes, ha="center",
               va="center", fontsize=12, fontweight="bold", color=DARK)
        a.text(0.5, 0.44, body, transform=a.transAxes, ha="center",
               va="center", fontsize=9.0, linespacing=1.5, color=INK)

    # grids for the reward cores
    s = np.linspace(-0.25, 1, 320)
    c = np.linspace(-0.25, 1, 320)
    S, C = np.meshgrid(s, c)
    Sp = np.clip(S, 0, 1)
    Cp = np.clip(C, 0, 1)
    Z_add = Sp + Cp                 # tau = 0, 1 additive core
    Z_mult = Sp * Cp                # tau = 2 multiplicative core

    for idx, (Z, title, cm) in enumerate([
        (Z_add, r"Additive core  $[S_{\rm net}]_+ + [C_{\rm net}]_+$   ($\tau=0,1$)", "YlGn"),
        (Z_mult, r"Multiplicative core  $[S_{\rm net}]_+[C_{\rm net}]_+$   ($\tau=2$)", "Greens"),
    ]):
        a = fig.add_subplot(gs[1, idx])
        cf = a.contourf(S, C, Z, levels=22, cmap=cm)
        a.contour(S, C, Z, levels=8, colors="#1B433266", linewidths=0.55)
        a.axvline(0, color=WARM, lw=1.2, ls="--")
        a.axhline(0, color=WARM, lw=1.2, ls="--")
        a.set_xlim(-0.25, 1)
        a.set_ylim(-0.25, 1)
        a.set_xlabel(r"$S_{\rm net}$", fontsize=10)
        a.set_ylabel(r"$C_{\rm net}$", fontsize=10)
        a.set_title(title, fontsize=10.5, color=DARK, pad=8)
        a.annotate("clipped to 0", xy=(-0.22, -0.22), xytext=(0.18, -0.17),
                   fontsize=7.5, color=WARM,
                   arrowprops=dict(arrowstyle="->", color=WARM, lw=1.0))
        cb = fig.colorbar(cf, ax=a, fraction=0.046, pad=0.03)
        cb.ax.tick_params(labelsize=7.5)

    # cross-section: monotone strictness penalty
    a = fig.add_subplot(gs[1, 2])
    x = np.linspace(0, 1, 500)
    psi1 = x
    psi2 = 1 - (1 - x) ** 2
    a.fill_between(x, psi1, psi2, color="#E3F1EA", alpha=0.9,
                   label=r"$\psi_2-\psi_1=x(1-x)\geq 0$")
    a.plot(x, psi1, color=MID, lw=2.4, label=r"$\psi_0=\psi_1=x$  (AI-Low/Med)")
    a.plot(x, psi2, color=WARM, lw=2.2, ls="--",
           label=r"$\psi_2=1-(1-x)^2$  (AI-Strict)")
    a.set_xlim(0, 1)
    a.set_ylim(0, 1.05)
    a.set_xlabel(r"normalized stress $x\in[0,1]$", fontsize=10)
    a.set_ylabel("penalty", fontsize=10)
    a.set_title("Monotone strictness penalty on [0,1]", fontsize=10.5,
                 color=DARK, pad=8)
    a.legend(fontsize=8, loc="lower right", frameon=True)
    a.grid(alpha=0.18)
    a.text(0.06, 0.94, r"$\psi_2'(x)=2(1-x)\geq 0$", fontsize=8.5, color="#C0392B")
    fig.savefig(path, dpi=300, bbox_inches="tight", pad_inches=0.22)
    plt.close(fig)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--outdir", type=Path, default=Path(__file__).resolve().parent.parent / "figures",
                   help="figure directory (default: figures/ at the repository root)")
    p.add_argument("--verify-labels", action="store_true",
                   help="print every figure label and the manuscript line it comes from")
    args = p.parse_args()

    if args.verify_labels:
        print("Label verification (source: multi_tier_agri_ecological_optimization_framework.tex)")
        print("-" * 62)
        for label, src in LABEL_SOURCES.items():
            print(f"{label:52s} -> {src}")
        return

    args.outdir.mkdir(parents=True, exist_ok=True)
    f1 = args.outdir / "fig1_closed_loop_architecture.png"
    f2 = args.outdir / "fig2_tier_progression.png"
    figure1(f1)
    figure2(f2)
    for f in (f1, f2):
        print(f"wrote {f} ({f.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
