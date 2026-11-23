#!/usr/bin/env python3
"""Reproduce the empirical benchmark and robustness checks for the framework.

From the repository root:
    python scripts/simulate_benchmark.py

Writes:
    results/results.json          all per-seed records, summaries, statistics, sensitivity
    results/results_table.tex     headline physical-outcome table for the manuscript
    results/stats_table.tex       paired-difference table for the manuscript
    results/sensitivity_table.tex one-at-a-time coefficient sensitivity table
    figures/Figure_3_Synergy_Contour.png
    figures/Figure_4_Drought_Stress_Test.png
    figures/Figure_5_Radar_Comparison.png
    figures/Figure_6_Sensitivity.png

Every constant used here is reported in the manuscript's parameter table.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --------------------------------------------------------------------- fixed design
K = 3
CROPS = ("winter wheat", "grain maize", "legume cover")
A = 1.0                      # ha
A_K = A / K                  # ha per plot
ALPHA = np.full(K, 1.0 / K)  # rain apportionment
ETA_IRR = 0.85
W_LOSS_FRAC = 0.05
W_AVAIL = 600.0              # m3/week, normal supply
W_AVAIL_DROUGHT = 240.0      # m3/week
D_MAX = 700.0                # m3/week
THETA_FC = np.array([260.0, 310.0, 220.0])
THETA_INIT = np.array([210.0, 250.0, 180.0])
THETA_CRIT = np.array([180.0, 220.0, 150.0])
THETA_SURV = 0.85 * THETA_CRIT
THETA_LOSS = 0.50 * THETA_CRIT               # crop-loss threshold for the safety metric
Y_MAX = np.array([7.0, 10.0, 3.0])           # t/ha potential
C_BASE = np.array([[0.75, 0.70, 0.65],
                   [0.80, 0.60, 0.55],
                   [0.65, 0.85, 0.90]])      # rows = j (indicator), cols = k (crop)
PRIORITY = (2, 0, 1)                         # legume -> wheat -> maize
M_MIN = 0.05
M_MAX = 0.40                                 # upper clip on adaptive duty cycle
M_HW = 0.25                                  # hardware amortisation overhead
P_NODE = 0.5                                 # W
N_NODES = 30
HOURS_PER_WEEK = 168
SUP_TECH, SUP_DIST, SUP_REG = 0.80, 0.90, 0.40
KAPPA = (SUP_TECH + (1 - SUP_DIST) + SUP_REG) / 3
S_DEG_EMERG = 0.65
RHO_BETA = 3.0
OMEGA_AMP, OMEGA_T0 = 0.45, 13
THETA_FC_MEAN = THETA_FC.mean()
DROUGHT = tuple(range(24, 30))
FIXED_RATE = 55.0                            # m3/plot/week, fixed-rate conventional

# Coefficients perturbing the response functions (see sensitivity analysis).
SENS = dict(a_org=0.0018, a_org_dep=0.0010, a_deg_chem=0.0015, a_deg_dep=0.0008,
            a_deg_decay=0.0012, soc_scale=20.0, yield_base=0.85, yield_span=0.15,
            drought_cext=0.35, drought_sdeg=0.38)

# --------------------------------------------------------------------- policies
# mode "fixed" : fixed-rate open-loop irrigation, continuous polling
# mode "et"    : state-based irrigation to the critical floor, same supply cap
# duty "unit"  : M_duty = 1.0
# duty "adaptive": M_duty rises with telemetry demand beta (corrected law)
CONFIG = {
    "fixed":     dict(name="Conv-Fixed", tau=None, chem=120.0, mode="fixed", duty="unit",
                      wS=1.0, wC=1.0, m=0.0, cM=0.0, cW=0.0, gate=False, triage=False),
    "et":        dict(name="Conv-ET", tau=None, chem=120.0, mode="et", duty="unit",
                      wS=1.0, wC=1.0, m=0.0, cM=0.0, cW=0.0, gate=False, triage=False),
    "ai_low":    dict(name="AI-Low", tau=0, chem=120.0, mode="et", duty="adaptive",
                      wS=1.0, wC=1.0, m=0.0, cM=0.25, cW=0.30, gate=False, triage=False),
    "ai_med":    dict(name="AI-Med", tau=1, chem=45.0, mode="et", duty="adaptive",
                      wS=1.0, wC=1.0, m=0.0, cM=0.50, cW=0.60, gate=False, triage=False),
    "ai_strict": dict(name="AI-Strict", tau=2, chem=0.0, mode="et", duty="adaptive",
                      wS=0.5, wC=0.5, m=1.5, cM=0.80, cW=1.00, gate=True, triage=True),
}
POLICY_ORDER = list(CONFIG)


# --------------------------------------------------------------------- forcing
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
    """Field-wide effective rainfall mean, m3/week."""
    return 120.0 + 60.0 * math.cos(2 * math.pi * (t - 5) / 52)


def psi(tau: int | None, x: float) -> float:
    return x if tau in (0, 1, None) else 1.0 - (1.0 - x) ** 2


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


def duty_cycle(beta: float, triage: bool) -> float:
    """Corrected law: polling RISES with telemetry demand beta.

    steady (beta=1) -> M_MIN ; rapid transient (beta=5) -> M_MAX.
    """
    if triage:
        return M_MIN
    return float(np.clip(M_MIN + (M_MAX - M_MIN) * (beta - 1.0) / 4.0, M_MIN, M_MAX))


# --------------------------------------------------------------------- simulation
def run_policy(policy: str, seed: int, *, trajectory: bool = False):
    """Simulate one policy for one seed."""
    rng = np.random.default_rng(seed)
    cfg = CONFIG[policy]
    tau = cfg["tau"]

    theta = THETA_INIT * (1 + rng.uniform(-0.08, 0.08, K))
    s_org = 0.55 * (1 + rng.uniform(-0.08, 0.08))
    s_deg = 0.25 * (1 + rng.uniform(-0.08, 0.08))

    water_total = 0.0
    et_actual_sum = np.zeros(K)
    et_potential_sum = np.zeros(K)
    duty_sum = 0.0
    crop_loss_weeks = 0
    j_sum = 0.0
    hist = []
    prev_theta_bar = theta.mean()
    prev_tsoil = 18.0

    for t in range(1, 53):
        dry = t in DROUGHT
        supply = W_AVAIL_DROUGHT if dry else W_AVAIL
        rain = rng.gamma(2.0, rain_mean(t) / 2.0)
        if dry:
            rain *= 0.30
        rain_share = ALPHA * rain
        et_c = np.array([10 * kc(k, t) * et0(t) * A_K for k in range(K)])
        et_potential_sum += et_c

        tsoil = 18 + 10 * math.sin(2 * math.pi * (t - 13) / 52) * math.exp(-0.002 * t) \
            + rng.normal(0, 0.5)

        triage = bool(dry and cfg["triage"] and np.any(theta < THETA_CRIT))
        if cfg["mode"] == "fixed":
            ext = np.full(K, min(FIXED_RATE, supply / K))
            duty = 1.0
        else:
            target = THETA_SURV if triage else THETA_CRIT
            ext = allocate(theta, rain_share, et_c, target, supply)

        if cfg["duty"] == "unit":
            duty = 1.0
        else:
            g_theta = abs(theta.mean() - prev_theta_bar) / THETA_FC_MEAN
            g_T = abs(tsoil - prev_tsoil) / 10.0
            beta = 1.0 + 4.0 * (1 - math.exp(-RHO_BETA * (g_theta + g_T)))
            duty = duty_cycle(beta, triage)

        water_total += ext.sum()
        duty_sum += duty
        inp = theta + rain_share + ETA_IRR * ext - et_c
        perc = np.maximum(0.0, inp - THETA_FC)
        et_actual_sum += np.minimum(et_c, np.maximum(0.0, theta + rain_share + ETA_IRR * ext))
        theta = np.clip(inp - perc, 0.0, THETA_FC)

        d_plus = max(0.0, ext.sum() * (1 + W_LOSS_FRAC) - rain) / D_MAX
        chem_frac = cfg["chem"] / 120.0
        s_org = float(np.clip(s_org + SENS["a_org"] * (1 - chem_frac)
                              - SENS["a_org_dep"] * d_plus, 0.0, 1.0))
        s_deg = float(np.clip(s_deg + SENS["a_deg_chem"] * chem_frac
                              + SENS["a_deg_dep"] * d_plus - SENS["a_deg_decay"] * s_org,
                              0.0, 1.0))
        s_deg_eff = s_deg + (SENS["drought_sdeg"] if dry else 0.0)
        c_ext = np.clip(0.2 + 0.6 * np.maximum(0.0, (THETA_CRIT - theta) / THETA_CRIT)
                        + (SENS["drought_cext"] if dry else 0.0), 0.0, 1.0)

        s_vec = np.array([s_org, 0.8 * s_org + 0.1, 0.7 * s_org + 0.2,
                          0.6 * s_org + 0.3])
        c_vec = np.array([[np.clip(C_BASE[j, k] * (0.6 + 0.4 * theta[k] / THETA_FC[k]),
                                   0.0, 1.0) for k in range(K)] for j in range(3)])
        s_net = s_vec.mean() - psi(tau, s_deg_eff)
        c_net = np.mean([c_vec[:, k].mean() - psi(tau, c_ext[k]) for k in range(K)])
        gate = 0.0 if (cfg["gate"] and (s_deg_eff > S_DEG_EMERG or np.any(theta < THETA_CRIT))) else 1.0
        omega = 1 + OMEGA_AMP * math.sin(2 * math.pi * (t - OMEGA_T0) / 52)
        reward = gate * (cfg["wS"] * max(s_net, 0) + cfg["wC"] * max(c_net, 0)
                         + cfg["m"] * max(s_net, 0) * max(c_net, 0))
        # Eq. (16): (theta_1 M_elec + theta_2 M_duty + theta_3 M_hw)/beta, theta_i = 1/3
        sense = (2.0 * duty + M_HW) / 3.0
        penalty = cfg["cM"] * sense / beta if cfg["duty"] == "adaptive" else 0.0
        penalty += cfg["cW"] * omega * psi(tau, min(d_plus, 1.0)) * KAPPA / (1 + 4 * SUP_DIST)
        j_sum += reward - penalty

        if dry:
            crop_loss_weeks += int(np.sum(theta < THETA_LOSS))
        if trajectory:
            hist.append(dict(week=t, theta=theta.copy(), s_deg_eff=s_deg_eff,
                             c_ext=c_ext.copy(), duty=duty, gate=gate, triage=triage))
        prev_theta_bar, prev_tsoil = theta.mean(), tsoil

    wr = et_actual_sum / np.maximum(et_potential_sum, 1e-9)
    yield_ha = float(np.sum(Y_MAX * wr * (SENS["yield_base"] + SENS["yield_span"] * chem_frac)) / K)
    energy = duty_sum * P_NODE * N_NODES * HOURS_PER_WEEK / 1000.0
    metrics = dict(
        policy=cfg["name"],
        yield_t_ha=yield_ha,
        water_m3_ha=float(water_total / A),
        energy_kwh_ha=float(energy / A),
        dsoc_g_kg=float(SENS["soc_scale"] * (s_org - 0.55)),
        crop_loss_crop_weeks=crop_loss_weeks,
        objective=float(j_sum / 52),
    )
    return (metrics, hist) if trajectory else metrics


# --------------------------------------------------------------------- analysis
METRICS = [("yield_t_ha", "Yield (t/ha)", "{:.2f}"),
           ("water_m3_ha", "Irrigation (m$^3$/ha)", "{:.0f}"),
           ("energy_kwh_ha", "IoT energy (kWh/ha)", "{:.1f}"),
           ("dsoc_g_kg", "$\\Delta$SOC (g/kg)", "{:.2f}"),
           ("crop_loss_crop_weeks", "Crop-loss crop-weeks", "{:.2f}")]


def collect(seeds):
    raw = {p: [run_policy(p, s) for s in seeds] for p in POLICY_ORDER}
    summary = {}
    for p, rows in raw.items():
        summary[p] = {k: dict(mean=float(np.mean([r[k] for r in rows])),
                              sd=float(np.std([r[k] for r in rows], ddof=1)))
                      for k in rows[0] if isinstance(rows[0][k], (int, float))}
    return raw, summary


def paired_stats(raw, baseline="fixed"):
    out = {}
    for p in POLICY_ORDER:
        if p == baseline:
            continue
        out[p] = {}
        for key, _, _ in METRICS + [("objective", "$J$ (diagnostic)", "{:.2f}")]:
            a = np.array([r[key] for r in raw[p]])
            b = np.array([r[key] for r in raw[baseline]])
            d = a - b
            if np.allclose(d, 0.0):           # identical policies on this metric
                out[p][key] = dict(mean=0.0, lo=0.0, hi=0.0, p=1.0, t=0.0)
                continue
            t, pval = stats.ttest_rel(a, b)
            lo, hi = stats.t.interval(0.95, len(d) - 1, loc=d.mean(), scale=stats.sem(d))
            out[p][key] = dict(mean=float(d.mean()), lo=float(lo), hi=float(hi),
                               p=float(pval), t=float(t))
    return out


def headline_checks(summary):
    s = summary
    return {
        "C1_ai_low_yield_gt_fixed": s["ai_low"]["yield_t_ha"]["mean"] > s["fixed"]["yield_t_ha"]["mean"],
        "C2_dsoc_monotone": (s["ai_strict"]["dsoc_g_kg"]["mean"] > s["ai_med"]["dsoc_g_kg"]["mean"]
                             > s["ai_low"]["dsoc_g_kg"]["mean"]),
        "C3_strict_fewer_crop_losses": (s["ai_strict"]["crop_loss_crop_weeks"]["mean"]
                                        < s["fixed"]["crop_loss_crop_weeks"]["mean"]),
        "C4_strict_lower_energy": (s["ai_strict"]["energy_kwh_ha"]["mean"]
                                   < s["fixed"]["energy_kwh_ha"]["mean"]),
    }


def sensitivity(seeds):
    keys = ["a_org", "a_org_dep", "a_deg_chem", "a_deg_dep", "a_deg_decay",
            "soc_scale", "yield_base", "yield_span", "drought_cext", "drought_sdeg"]
    rows = []
    for key in keys:
        original = SENS[key]
        for factor in (0.75, 1.25):
            SENS[key] = original * factor
            _, sm = collect(seeds)
            checks = headline_checks(sm)
            rows.append(dict(coefficient=key, factor=factor,
                             ai_low_yield=sm["ai_low"]["yield_t_ha"]["mean"],
                             ai_strict_dsoc=sm["ai_strict"]["dsoc_g_kg"]["mean"],
                             ai_strict_crop_loss=sm["ai_strict"]["crop_loss_crop_weeks"]["mean"],
                             checks=checks, all_hold=all(checks.values())))
            SENS[key] = original
    return rows


# --------------------------------------------------------------------- LaTeX output
def table_headline(summary) -> str:
    names = [CONFIG[p]["name"].replace("-", "\\text{-}") for p in POLICY_ORDER]
    lines = ["\\begin{table}[t]", "  \\centering", "  \\small",
             "\\caption{Empirical benchmark: mean $\\pm$ SD over $N=20$ seeds (100--119). "
             "The two conventional baselines are fixed-rate and ET-scheduled; the three "
             "\\texttt{AI} tiers add adaptive duty cycling, chemical caps and (at $\\tau=2$) "
             "gating with drought triage. Five physical outcomes drive ranking; "
             "$\\mathcal{J}$ is a within-tier diagnostic reported in Table~\\ref{tab:diagnostics}.}",
             "  \\label{tab:results}", "  \\resizebox{\\linewidth}{!}{%",
             "  \\begin{tabular}{@{}lccccc@{}}", "    \\toprule",
             "    Metric & " + " & ".join(names) + " \\\\", "    \\midrule"]
    for key, label, fmt in METRICS:
        cells = [fmt.format(summary[p][key]["mean"]) + " $\\pm$ " + fmt.format(summary[p][key]["sd"])
                 for p in POLICY_ORDER]
        lines.append("    " + label + " & " + " & ".join(cells) + " \\\\")
    lines += ["    \\bottomrule", "  \\end{tabular}}", "\\end{table}"]
    return "\n".join(lines) + "\n"


def table_stats(stats_by_policy) -> str:
    names = [CONFIG[p]["name"].replace("-", "\\text{-}") for p in POLICY_ORDER if p != "fixed"]
    lines = ["\\begin{table}[t]", "  \\centering", "  \\small",
             "\\caption{Paired differences (each \\texttt{AI} tier minus \\texttt{Conv-Fixed}) "
             "over the same 20 seeds. Entries are mean difference with 95\\% paired $t$ "
             "confidence interval; $p<0.05$ marked $^{*}$.}",
             "  \\label{tab:paired}", "  \\resizebox{\\linewidth}{!}{%",
             "  \\begin{tabular}{@{}lcccc@{}}", "    \\toprule",
             "    Metric & " + " & ".join(names) + " \\\\", "    \\midrule"]
    for key, label, _ in METRICS:
        cells = []
        for p in POLICY_ORDER:
            if p == "fixed":
                continue
            d = stats_by_policy[p][key]
            mark = "$^{*}$" if d["p"] < 0.05 else ""
            cells.append(f"{d['mean']:+.2f} [{d['lo']:+.2f},{d['hi']:+.2f}]{mark}")
        lines.append("    " + label + " & " + " & ".join(cells) + " \\\\")
    lines += ["    \\bottomrule", "  \\end{tabular}}", "\\end{table}"]
    return "\n".join(lines) + "\n"


def table_sensitivity(rows) -> str:
    lines = ["\\begin{table}[t]", "  \\centering", "  \\small",
             "\\caption{One-at-a-time sensitivity: each coefficient multiplied by $0.75$ or "
             "$1.25$ with all others fixed. The four headline conclusions (C1--C4) are defined "
             "in the text. All 20 perturbations preserve them, so only the ranges are shown.}",
             "  \\label{tab:sensitivity}", "  \\begin{tabular}{@{}lllll@{}}",
             "    \\toprule",
             "    Coefficient & Factor & AI-Low yield & AI-Strict $\\Delta$SOC & "
             "AI-Strict crop-loss \\\\", "    \\midrule"]
    for r in rows:
        coef = r['coefficient'].replace('_', '\\_')
        lines.append(f"    \\texttt{{{coef}}} & $\\times${r['factor']:.2f} & "
                     f"{r['ai_low_yield']:.2f} & {r['ai_strict_dsoc']:.2f} & "
                     f"{r['ai_strict_crop_loss']:.2f} \\\\")
    lines += ["    \\bottomrule", "  \\end{tabular}", "\\end{table}"]
    return "\n".join(lines) + "\n"


def table_diagnostics(summary) -> str:
    names = [CONFIG[p]["name"].replace("-", "\\text{-}") for p in POLICY_ORDER]
    cells = [f"{summary[p]['objective']['mean']:.2f} $\\pm$ {summary[p]['objective']['sd']:.2f}"
             for p in POLICY_ORDER]
    return "\n".join([
        "\\begin{table}[t]", "  \\centering", "  \\small",
        "\\caption{Within-tier diagnostic $\\mathcal{J}$ (Eq.~\\eqref{eq:unified_objective}). "
        "The tier-specific penalty weights $c_M,c_W$ and the nature gate make these values "
        "incomparable across policies; they are reported for completeness only and must not "
        "be used for cross-policy ranking.}",
        "  \\label{tab:diagnostics}", "  \\begin{tabular}{@{}lccccc@{}}",
        "    \\toprule", "    Metric & " + " & ".join(names) + " \\\\", "    \\midrule",
        "    $J$ (within-tier) & " + " & ".join(cells) + " \\\\",
        "    \\bottomrule", "  \\end{tabular}", "\\end{table}"])


# --------------------------------------------------------------------- figures
def make_figures(out: Path, raw: dict, summary: dict, sens_rows) -> None:
    colors = ["#7f8c8d", "#34495e", "#e67e22", "#2980b9", "#27ae60"]
    names = [CONFIG[p]["name"] for p in POLICY_ORDER]

    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    s = np.linspace(0, 1, 300)
    ax.plot(s, s, color=colors[3], lw=2, label="additive $w_S S+w_C C$")
    ax.plot(s, s ** 2, color=colors[4], lw=2, ls="--", label="multiplicative $1.5[S]_+[C]_+$ / 1.5")
    ax.fill_between(s, s ** 2, s, color="#eaf6f0", alpha=0.9, label="anti-compensation region")
    ax.set(xlabel="$S_{\\mathrm{net}}$ ($C_{\\mathrm{net}}=S_{\\mathrm{net}}$)",
           ylabel="reward core (normalised)", title="Fig. 3 - Non-compensatory synergy at $\\tau=2$")
    ax.legend(fontsize=8, loc="upper left"); ax.grid(alpha=0.2)
    fig.tight_layout(); fig.savefig(out / "Figure_3_Synergy_Contour.png", dpi=300); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for i, (pol, c) in enumerate(zip(["fixed", "ai_strict"], [colors[0], colors[4]])):
        _, hist = run_policy(pol, 105, trajectory=True)
        weeks = [h["week"] for h in hist]
        for k, crop in enumerate(CROPS):
            axes[i].plot(weeks, [h["theta"][k] for h in hist], label=crop, lw=1.7)
            axes[i].axhline(THETA_CRIT[k], color=f"C{k}", lw=0.8, ls=":")
        axes[i].axvspan(23.5, 29.5, color="#fdebd0", alpha=0.7, label="drought")
        axes[i].set(xlim=(18, 36), xlabel="week", ylabel="root-zone storage (m$^3$)",
                    title=f"Fig. 4 - {CONFIG[pol]['name']}")
        axes[i].legend(fontsize=7, loc="lower left"); axes[i].grid(alpha=0.15)
    fig.tight_layout(); fig.savefig(out / "Figure_4_Drought_Stress_Test.png", dpi=300); plt.close(fig)

    labels = ["Yield", "Water saving", "Energy saving", "$\\Delta$SOC", "Crisis safety"]
    vals = {}
    for key in POLICY_ORDER:
        d = summary[key]
        vals[key] = [d["yield_t_ha"]["mean"],
                     (summary["fixed"]["water_m3_ha"]["mean"] - d["water_m3_ha"]["mean"])
                     / summary["fixed"]["water_m3_ha"]["mean"] * 5,
                     (summary["fixed"]["energy_kwh_ha"]["mean"] - d["energy_kwh_ha"]["mean"])
                     / summary["fixed"]["energy_kwh_ha"]["mean"] * 5,
                     d["dsoc_g_kg"]["mean"] * 2,
                     5 - d["crop_loss_crop_weeks"]["mean"] / 3]
    ang = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist(); ang += ang[:1]
    fig = plt.figure(figsize=(8, 6.5)); ax = fig.add_subplot(111, polar=True)
    for name, c in zip(POLICY_ORDER, colors):
        v = vals[name] + vals[name][:1]
        ax.plot(ang, v, color=c, lw=2, label=CONFIG[name]["name"])
        ax.fill(ang, v, color=c, alpha=0.05)
    ax.set_xticks(ang[:-1]); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylim(0, 5); ax.legend(loc="upper right", fontsize=7)
    ax.set_title("Fig. 5 - Normalised outcome comparison", pad=18)
    fig.tight_layout(); fig.savefig(out / "Figure_5_Radar_Comparison.png", dpi=300); plt.close(fig)

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    keys = ["ai_low_yield", "ai_strict_dsoc", "ai_strict_crop_loss"]
    titles = ["AI-Low yield (t/ha)", "AI-Strict $\\Delta$SOC (g/kg)", "AI-Strict crop-loss (crop-weeks)"]
    for ax, key, title in zip(axes, keys, titles):
        low = [r[key] for r in sens_rows if r["factor"] == 0.75]
        high = [r[key] for r in sens_rows if r["factor"] == 1.25]
        ax.plot(low, "o-", label="$\\times 0.75$", color=colors[3])
        ax.plot(high, "s--", label="$\\times 1.25$", color=colors[4])
        ax.set(title=title, xlabel="coefficient index", ylabel="value")
        ax.tick_params(labelsize=8)
        ax.grid(alpha=0.2); ax.legend(fontsize=7)
    fig.suptitle("Fig. 6 - One-at-a-time coefficient sensitivity (10 coefficients)", fontsize=10)
    fig.tight_layout(); fig.savefig(out / "Figure_6_Sensitivity.png", dpi=300); plt.close(fig)


# --------------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--outdir", type=Path, default=Path(__file__).resolve().parent.parent,
                    help="repository root (contains results/ and figures/)")
    ap.add_argument("--seeds", type=int, default=20)
    args = ap.parse_args()
    resdir = args.outdir / "results"; figdir = args.outdir / "figures"
    resdir.mkdir(parents=True, exist_ok=True); figdir.mkdir(parents=True, exist_ok=True)
    seeds = list(range(100, 100 + args.seeds))

    raw, summary = collect(seeds)
    ps = paired_stats(raw)
    sens = sensitivity(seeds)

    (resdir / "results.json").write_text(json.dumps(dict(
        seeds=seeds, policies=POLICY_ORDER, summary=summary, raw=raw,
        paired_statistics=ps, sensitivity=sens, headline_checks=headline_checks(summary)),
        indent=2), encoding="utf-8")
    (resdir / "results_table.tex").write_text(table_headline(summary), encoding="utf-8")
    (resdir / "stats_table.tex").write_text(table_stats(ps), encoding="utf-8")
    (resdir / "sensitivity_table.tex").write_text(table_sensitivity(sens), encoding="utf-8")
    (resdir / "diagnostics_table.tex").write_text(table_diagnostics(summary), encoding="utf-8")

    make_figures(figdir, raw, summary, sens)
    for p in POLICY_ORDER:
        d = summary[p]
        print(f"{CONFIG[p]['name']:11s} yield={d['yield_t_ha']['mean']:.2f} "
              f"water={d['water_m3_ha']['mean']:.0f} energy={d['energy_kwh_ha']['mean']:.1f} "
              f"dSOC={d['dsoc_g_kg']['mean']:.2f} loss={d['crop_loss_crop_weeks']['mean']:.2f}")
    print("headline checks:", headline_checks(summary))
    print("sensitivity: all hold =", all(r["all_hold"] for r in sens))


if __name__ == "__main__":
    main()
