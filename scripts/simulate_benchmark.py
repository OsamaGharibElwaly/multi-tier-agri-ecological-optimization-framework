#!/usr/bin/env python3
"""Reproduce the empirical benchmark for the multi-tier agri-ecological framework.

Runs 4 policies x 20 seeds over 52 weeks and writes, relative to the repo root:
  results/results.json          full per-seed metrics
  results/results_table.tex     LaTeX table (mean +/- SD) for the manuscript
  figures/Figure_3_Synergy_Contour.png
  figures/Figure_4_Drought_Stress_Test.png
  figures/Figure_5_Radar_Comparison.png

Every constant used here is reported in the manuscript's parameter table.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ---------------------------------------------------------------------- fixed design
K = 3
CROPS = ("winter wheat", "grain maize", "legume cover")
A = 1.0                      # ha
A_K = A / K                  # ha per plot
ALPHA = np.full(K, 1.0 / K)  # rain apportionment
ETA_IRR = 0.85
W_LOSS_FRAC = 0.05
W_AVAIL = 600.0              # m3/week, recalibrated normal supply
W_AVAIL_DROUGHT = 240.0      # m3/week
D_MAX = 700.0                # m3/week
THETA_FC = np.array([260.0, 310.0, 220.0])
THETA_INIT = np.array([210.0, 250.0, 180.0])
THETA_CRIT = np.array([180.0, 220.0, 150.0])
THETA_SURV = 0.85 * THETA_CRIT
THETA_LOSS = 0.50 * THETA_CRIT               # crop-loss threshold used for the safety metric
Y_MAX = np.array([7.0, 10.0, 3.0])          # t/ha potential
C_BASE = np.array([[0.75, 0.70, 0.65],      # nutritional / biodiversity / varietal
                   [0.80, 0.60, 0.55],
                   [0.65, 0.85, 0.90]])     # rows = j, cols = k
PRIORITY = (2, 0, 1)                        # legume -> wheat -> maize
M_MIN = 0.05
P_NODE = 0.5                                # W
N_NODES = 30
HOURS_PER_WEEK = 168
SUP_TECH, SUP_DIST, SUP_REG = 0.80, 0.90, 0.40
KAPPA = (SUP_TECH + (1 - SUP_DIST) + SUP_REG) / 3
S_DEG_EMERG = 0.65
RHO_BETA = 3.0
OMEGA_AMP, OMEGA_T0 = 0.45, 13
THETA_FC_MEAN = THETA_FC.mean()
SOC_SCALE = 20.0                            # g/kg per unit S_org
TIERS = {
    0: dict(name="AI-Low",    chem=120.0, wS=1.0, wC=1.0, m=0.0, cM=0.25, cW=0.30),
    1: dict(name="AI-Med",    chem=45.0,  wS=1.0, wC=1.0, m=0.0, cM=0.50, cW=0.60),
    2: dict(name="AI-Strict", chem=0.0,   wS=0.5, wC=0.5, m=1.5, cM=0.80, cW=1.00),
}
DROUGHT = tuple(range(24, 30))              # Weeks 24-29 inclusive


def et0(t: int) -> float:
    """Reference evapotranspiration, mm/week, range [15, 42], peak week 26."""
    return 28.5 + 13.5 * math.sin(2 * math.pi * (t - 13) / 52)


def kc(k: int, t: int) -> float:
    """Crop coefficient: wheat spring peak, maize summer peak, legume autumn peak."""
    if k == 0:
        return 0.40 + 0.70 * math.exp(-((t - 12) / 8.0) ** 2)
    if k == 1:
        return 0.40 + 0.80 * math.exp(-((t - 26) / 9.0) ** 2)
    return 0.35 + 0.55 * math.exp(-((t - 35) / 10.0) ** 2)


def rain_mean(t: int) -> float:
    """Field-wide effective rainfall mean, m3/week, wet spring/autumn, dry summer."""
    return 120.0 + 60.0 * math.cos(2 * math.pi * (t - 5) / 52)


def psi(tau: int, x: float) -> float:
    return x if tau in (0, 1) else 1.0 - (1.0 - x) ** 2


def allocate(theta, rain_share, et, target, supply):
    """Priority-ordered greedy allocation capped at the requested maintenance target."""
    req = np.maximum(0.0, (target - theta - rain_share + et) / ETA_IRR)
    out = np.zeros(K)
    left = supply
    for k in PRIORITY:
        a = min(req[k], left)
        out[k] = a
        left -= a
    return out


def run_policy(tau: int | None, seed: int, *, trajectory: bool = False):
    """Simulate one policy for one seed. tau=None is the Conventional policy."""
    rng = np.random.default_rng(seed)
    conventional = tau is None
    tier = TIERS.get(tau, dict(name="Conventional", chem=120.0,
                               wS=1.0, wC=1.0, m=0.0, cM=0.0, cW=0.0))

    theta = THETA_INIT * (1 + rng.uniform(-0.08, 0.08, K))
    s_org = 0.55 * (1 + rng.uniform(-0.08, 0.08))
    s_deg = 0.25 * (1 + rng.uniform(-0.08, 0.08))

    water_total = 0.0
    et_actual_sum = np.zeros(K)
    et_potential_sum = np.zeros(K)
    duty_sum = 0.0
    crisis_weeks = 0
    j_sum = 0.0
    hist = []
    prev_theta_bar = theta.mean()
    prev_tsoil = 18.0

    for t in range(1, 53):
        dry = t in DROUGHT
        supply = W_AVAIL_DROUGHT if dry else W_AVAIL
        rain = rng.gamma(2.0, rain_mean(t) / 2.0)
        if dry:
            rain *= 0.30                       # 70% reduction
        rain_share = ALPHA * rain
        et_c = np.array([10 * kc(k, t) * et0(t) * A_K for k in range(K)])
        et_potential_sum += et_c

        tsoil = 18 + 10 * math.sin(2 * math.pi * (t - 13) / 52) * math.exp(-0.002 * t) \
            + rng.normal(0, 0.5)

        if conventional:
            ext = np.full(K, min(55.0, supply / K))
            duty = 1.0
            triage = False
        else:
            triage = dry and tau == 2 and bool(np.any(theta < THETA_CRIT))
            target = THETA_SURV if triage else THETA_CRIT
            ext = allocate(theta, rain_share, et_c, target, supply)
            g_theta = abs(theta.mean() - prev_theta_bar) / THETA_FC_MEAN
            g_T = abs(tsoil - prev_tsoil) / 10.0
            beta = 1.0 + 4.0 * (1 - math.exp(-RHO_BETA * (g_theta + g_T)))
            duty = M_MIN if triage else float(np.clip(M_MIN + 0.35 / beta, M_MIN, 0.40))

        water_total += ext.sum()
        duty_sum += duty
        inp = theta + rain_share + ETA_IRR * ext - et_c
        perc = np.maximum(0.0, inp - THETA_FC)
        et_actual_sum += np.minimum(et_c, np.maximum(0.0, theta + rain_share + ETA_IRR * ext))
        theta = np.clip(inp - perc, 0.0, THETA_FC)

        d_plus = max(0.0, ext.sum() * (1 + W_LOSS_FRAC) - rain) / D_MAX
        s_org = float(np.clip(s_org + 0.0018 * (1 - tier["chem"] / 120.0)
                              - 0.0010 * d_plus, 0.0, 1.0))
        s_deg = float(np.clip(s_deg + 0.0015 * (tier["chem"] / 120.0)
                              + 0.0008 * d_plus - 0.0012 * s_org, 0.0, 1.0))
        s_deg_eff = s_deg + (0.38 if dry else 0.0)
        c_ext = np.clip(0.2 + 0.6 * np.maximum(0.0, (THETA_CRIT - theta) / THETA_CRIT)
                        + (0.35 if dry else 0.0), 0.0, 1.0)

        s_vec = np.array([s_org, 0.8 * s_org + 0.1, 0.7 * s_org + 0.2,
                          0.6 * s_org + 0.3])
        c_vec = np.array([[np.clip(C_BASE[j, k] * (0.6 + 0.4 * theta[k] / THETA_FC[k]),
                                   0.0, 1.0) for k in range(K)] for j in range(3)])
        s_net = s_vec.mean() - psi(tau or 0, s_deg_eff)
        c_net = np.mean([c_vec[:, k].mean() - psi(tau or 0, c_ext[k]) for k in range(K)])
        gate = 1.0
        if tau == 2 and (s_deg_eff > S_DEG_EMERG or np.any(theta < THETA_CRIT)):
            gate = 0.0
        omega = 1 + OMEGA_AMP * math.sin(2 * math.pi * (t - OMEGA_T0) / 52)
        reward = gate * (tier["wS"] * max(s_net, 0) + tier["wC"] * max(c_net, 0)
                         + tier["m"] * max(s_net, 0) * max(c_net, 0))
        penalty = tier["cM"] * duty / beta if not conventional else 0.0
        penalty += tier["cW"] * omega * psi(tau or 0, min(d_plus, 1.0)) * KAPPA / (1 + 4 * SUP_DIST)
        j_sum += reward - penalty

        if dry:
            crisis_weeks += int(np.sum(theta < THETA_LOSS))
        if trajectory:
            hist.append(dict(week=t, theta=theta.copy(), s_deg_eff=s_deg_eff,
                             c_ext=c_ext.copy(), duty=duty, gate=gate, triage=triage))
        prev_theta_bar, prev_tsoil = theta.mean(), tsoil

    wr = et_actual_sum / np.maximum(et_potential_sum, 1e-9)
    yield_ha = float(np.sum(Y_MAX * wr * (0.85 + 0.15 * tier["chem"] / 120.0)) / K)
    energy = water_total * 0.0 + duty_sum * P_NODE * N_NODES * HOURS_PER_WEEK / 1000.0
    metrics = dict(
        policy=tier["name"],
        yield_t_ha=yield_ha,
        water_m3_ha=float(water_total / A),
        energy_kwh_ha=float(energy / A),
        dsoc_g_kg=float(SOC_SCALE * (s_org - 0.55)),
        crisis_crop_weeks=crisis_weeks,
        objective=float(j_sum / 52),
    )
    return (metrics, hist) if trajectory else metrics


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", type=Path, default=Path(__file__).resolve().parent.parent,
                    help="repository root (contains results/ and figures/)")
    ap.add_argument("--seeds", type=int, default=20)
    args = ap.parse_args()
    resdir = args.outdir / "results"
    figdir = args.outdir / "figures"
    resdir.mkdir(parents=True, exist_ok=True)
    figdir.mkdir(parents=True, exist_ok=True)
    seeds = list(range(100, 100 + args.seeds))
    policies = [(None, "Conventional"), (0, "AI-Low"), (1, "AI-Med"), (2, "AI-Strict")]

    raw = {}
    for tau, name in policies:
        raw[name] = [run_policy(tau, s) for s in seeds]

    summary = {}
    for name, rows in raw.items():
        summary[name] = {
            k: dict(mean=float(np.mean([r[k] for r in rows])),
                    sd=float(np.std([r[k] for r in rows], ddof=1)))
            for k in rows[0] if isinstance(rows[0][k], (int, float))
        }

    (resdir / "results.json").write_text(
        json.dumps(dict(seeds=seeds, summary=summary,
                        raw={k: v for k, v in raw.items()}), indent=2), encoding="utf-8")

    keys = [("yield_t_ha", "Yield (t/ha)"), ("water_m3_ha", "Irrigation (m$^3$/ha)"),
            ("energy_kwh_ha", "IoT energy (kWh/ha)"), ("dsoc_g_kg", "$\\Delta$SOC (g/kg)"),
            ("crisis_crop_weeks", "Crop-loss crop-weeks"), ("objective", "$J$ (diagnostic)")]
    lines = ["\\begin{table}[t]", "  \\centering", "  \\small",
             "  \\caption{Empirical benchmark results: mean $\\pm$ SD over $N=20$ seeds "
             "(100--119). The five primary physical metrics drive cross-policy ranking; "
             "$\\mathcal{J}$ is a within-tier diagnostic only.}",
             "  \\label{tab:results}",
             "  \\resizebox{\\linewidth}{!}{%",
             "  \\begin{tabular}{@{}l" + "c" * len(policies) + "@{}}",
             "    \\toprule",
             "    Metric & " + " & ".join(p[1].replace("-", "\\text{-}") for p in policies) + " \\\\",
             "    \\midrule"]
    for key, label in keys:
        cells = []
        for _, name in policies:
            d = summary[name][key]
            fmt = "{:.1f}" if key in ("water_m3_ha", "energy_kwh_ha") else "{:.2f}"
            cells.append(f"${fmt.format(d['mean'])} \\pm {fmt.format(d['sd'])}$")
        lines.append(f"    {label} & " + " & ".join(cells) + " \\\\")
    lines += ["    \\bottomrule", "  \\end{tabular}}", "\\end{table}"]
    (resdir / "results_table.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")

    make_figures(figdir, raw, summary)
    for name, d in summary.items():
        print(f"{name:12s} yield={d['yield_t_ha']['mean']:.2f} water={d['water_m3_ha']['mean']:.0f} "
              f"energy={d['energy_kwh_ha']['mean']:.1f} dSOC={d['dsoc_g_kg']['mean']:.2f} "
              f"crisis={d['crisis_crop_weeks']['mean']:.2f}")


def make_figures(out: Path, raw: dict, summary: dict) -> None:
    colors = ["#7f8c8d", "#e67e22", "#2980b9", "#27ae60"]
    names = ["Conventional", "AI-Low", "AI-Med", "AI-Strict"]

    # Fig 3: additive vs multiplicative reward core at tau=2
    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    s = np.linspace(0, 1, 300)
    ax.plot(s, s, color=colors[2], lw=2, label="additive $w_S S+w_C C$")
    ax.plot(s, s ** 2, color=colors[3], lw=2, ls="--", label="multiplicative $1.5[S]_+[C]_+$ / 1.5")
    ax.fill_between(s, s ** 2, s, color="#eaf6f0", alpha=0.9, label="anti-compensation region")
    ax.set(xlabel="$S_{\\mathrm{net}}$ ($C_{\\mathrm{net}}=S_{\\mathrm{net}}$)",
           ylabel="reward core (normalised)", title="Fig. 3 — Non-compensatory synergy at $\\tau=2$")
    ax.legend(fontsize=8, loc="upper left")
    ax.grid(alpha=0.2)
    fig.tight_layout()
    fig.savefig(out / "Figure_3_Synergy_Contour.png", dpi=300)
    plt.close(fig)

    # Fig 4: drought trajectories, one representative seed
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for i, (name, c) in enumerate(zip(["Conventional", "AI-Strict"], [colors[0], colors[3]])):
        _, hist = run_policy(None if name == "Conventional" else 2, 105, trajectory=True)
        weeks = [h["week"] for h in hist]
        for k, crop in enumerate(CROPS):
            axes[i].plot(weeks, [h["theta"][k] for h in hist], label=crop, lw=1.7)
            axes[i].axhline(THETA_CRIT[k], color=f"C{k}", lw=0.8, ls=":")
        axes[i].axvspan(23.5, 29.5, color="#fdebd0", alpha=0.7, label="drought")
        axes[i].set(xlim=(18, 36), xlabel="week", ylabel="root-zone storage (m³)",
                    title=f"Fig. 4 — {name}")
        axes[i].legend(fontsize=7, loc="lower left")
        axes[i].grid(alpha=0.15)
    fig.tight_layout()
    fig.savefig(out / "Figure_4_Drought_Stress_Test.png", dpi=300)
    plt.close(fig)

    # Fig 5: radar of normalised outcomes
    labels = ["Yield", "Water saving", "Energy saving", "ΔSOC", "Crisis safety"]
    vals = {}
    for key in summary:
        d = summary[key]
        vals[key] = [d["yield_t_ha"]["mean"],
                     (summary["Conventional"]["water_m3_ha"]["mean"] - d["water_m3_ha"]["mean"])
                     / summary["Conventional"]["water_m3_ha"]["mean"] * 5,
                     (summary["Conventional"]["energy_kwh_ha"]["mean"] - d["energy_kwh_ha"]["mean"])
                     / summary["Conventional"]["energy_kwh_ha"]["mean"] * 5,
                     d["dsoc_g_kg"]["mean"] * 2,
                     5 - d["crisis_crop_weeks"]["mean"] / 3]
    ang = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    ang += ang[:1]
    fig = plt.figure(figsize=(7, 6))
    ax = fig.add_subplot(111, polar=True)
    for name, c in zip(names, colors):
        v = vals[name] + vals[name][:1]
        ax.plot(ang, v, color=c, lw=2, label=name)
        ax.fill(ang, v, color=c, alpha=0.06)
    ax.set_xticks(ang[:-1])
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 5)
    ax.legend(loc="upper right", fontsize=7)
    ax.set_title("Fig. 5 — Normalised outcome comparison", pad=18)
    fig.tight_layout()
    fig.savefig(out / "Figure_5_Radar_Comparison.png", dpi=300)
    plt.close(fig)


if __name__ == "__main__":
    main()
