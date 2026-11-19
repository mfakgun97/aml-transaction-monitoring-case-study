"""Static report figures (PNG) for the README and decision proposal.

Palette: a validated categorical order (blue, orange) with neutral greys for
'context' marks; thin marks, recessive grid, direct labels instead of a
number on every point.
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from . import config as C  # noqa: E402

SURFACE = "#fcfcfb"
TEXT = "#0b0b0b"
TEXT_2 = "#52514e"
GRID = "#e4e3df"
BLUE = "#2a78d6"
BLUE_LIGHT = "#9ec5f4"
ORANGE = "#eb6834"
NEUTRAL = "#c9c8c2"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": GRID, "axes.labelcolor": TEXT_2, "xtick.color": TEXT_2, "ytick.color": TEXT_2,
    "text.color": TEXT, "font.size": 10.5, "axes.titlesize": 13, "axes.titleweight": "bold",
    "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8, "axes.axisbelow": True,
    "legend.frameon": False,
})


def _subtitle(ax, text):
    ax.text(0, 1.02, text, transform=ax.transAxes, color=TEXT_2, fontsize=10, va="bottom")


def _save(fig, name):
    fig.tight_layout()
    fig.savefig(C.FIGURES_DIR / name, dpi=160)
    plt.close(fig)


def rule_alerts(rule_perf: pd.DataFrame, overall: dict):
    d = rule_perf.iloc[::-1]
    fp = d.alerts_per_month - d.true_positives / len(C.TEST_MONTHS)
    tp = d.true_positives / len(C.TEST_MONTHS)
    labels = [f"{r.split('_')[0]}  {desc}" for r, desc in zip(d.rule, d.description)]
    fig, ax = plt.subplots(figsize=(11, 4.4))
    ax.barh(labels, tp, color=BLUE, height=0.55, label="Suspicious (true positive)")
    ax.barh(labels, fp, left=tp, color=NEUTRAL, height=0.55, label="Not suspicious (false positive)",
            edgecolor=SURFACE, linewidth=2)
    for y, (t, f, p) in enumerate(zip(tp, fp, d.precision)):
        ax.text(t + f + 3, y, f"{t + f:.0f}/month · {p:.0%} precise", va="center", color=TEXT_2, fontsize=9.5)
    ax.set_xlabel("Alerts per month (test period, rules overlap)")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, (tp + fp).max() * 1.5)
    ax.legend(loc="lower right")
    ax.set_title("Current rules generate a lot of noise", pad=26)
    _subtitle(ax, f"{overall['alerts_per_month']:.0f} alerts/month in total; {overall['precision']:.1%} turn out to be suspicious")
    _save(fig, "01_rule_alerts.png")


def options_chart(options: list[dict], capacity: int):
    d = pd.DataFrame(options)
    lo = [r - ci[0] for r, ci in zip(d.recall, d.recall_ci_95)]
    hi = [ci[1] - r for r, ci in zip(d.recall, d.recall_ci_95)]
    colors = [NEUTRAL, BLUE_LIGHT, BLUE, BLUE_LIGHT]
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.bar(d.label, d.recall, color=colors, width=0.55, yerr=[lo, hi], ecolor=TEXT_2, capsize=4, error_kw={"linewidth": 1})
    for i, (r, n) in enumerate(zip(d.recall, d.suspicious_cases_caught)):
        ax.text(i, d.recall_ci_95[i][1] + 0.03, f"{r:.0%}\n({n:.0f} cases)", ha="center", color=TEXT, fontsize=10)
    ax.set_ylim(0, 1.18)
    ax.set_yticks([0, .25, .5, .75, 1.0], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_ylabel("Share of suspicious activity caught")
    ax.grid(axis="x", visible=False)
    ax.set_title("Same team, very different outcomes", pad=26)
    _subtitle(ax, f"Out-of-time test (May–Jun), {capacity} reviews/month for every option · bars = 95% bootstrap CI · darker = recommended")
    _save(fig, "02_options_recall.png")


def capacity_curve(curve: pd.DataFrame, rules: dict, options: list[dict], capacity: int):
    a = next(o for o in options if o["option"] == "A")
    fig, ax = plt.subplots(figsize=(10, 4.6))
    ax.plot(curve.alerts_per_month, curve.recall, color=BLUE, linewidth=2, label="ML risk ranking")
    ax.scatter([rules["alerts_per_month"]], [rules["recall_if_all_reviewed"]], s=70, color=ORANGE, zorder=3,
               edgecolor=SURFACE, linewidth=2, label="Rules")
    ax.scatter([capacity], [a["recall"]], s=70, color=ORANGE, zorder=3, edgecolor=SURFACE, linewidth=2)
    ax.annotate("Rules, every alert reviewed", (rules["alerts_per_month"], rules["recall_if_all_reviewed"]),
                xytext=(10, -16), textcoords="offset points", color=TEXT_2, fontsize=9.5)
    ax.annotate("Rules, today (FIFO within capacity)", (capacity, a["recall"]),
                xytext=(10, -14), textcoords="offset points", color=TEXT_2, fontsize=9.5)
    ax.axvline(capacity, color=TEXT_2, linestyle=(0, (4, 3)), linewidth=1)
    ax.text(capacity + 4, 0.03, "team capacity", color=TEXT_2, fontsize=9.5)
    ax.set_ylim(0, 1.02)
    ax.set_yticks([0, .25, .5, .75, 1.0], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("Alerts reviewed per month")
    ax.set_ylabel("Share of suspicious activity caught")
    ax.legend(loc="lower right")
    ax.set_title("Detection vs. workload", pad=26)
    _subtitle(ax, "The ML ranking catches more at every workload level than the rules do at any level")
    _save(fig, "03_capacity_curve.png")


def ml_slots(slots: pd.DataFrame):
    fig, ax = plt.subplots(figsize=(10, 4.2))
    ax.plot(slots.ml_slots, slots.recall, color=BLUE, linewidth=2, marker="o", markersize=6,
            markeredgecolor=SURFACE, markeredgewidth=2)
    chosen = slots.set_index("ml_slots").recall.get(C.ML_SCENARIO_SLOTS)
    if chosen is not None:
        ax.annotate(f"Proposed: {C.ML_SCENARIO_SLOTS} slots → {chosen:.0%}", (C.ML_SCENARIO_SLOTS, chosen), xytext=(8, -26),
                    textcoords="offset points", color=TEXT, fontsize=10)
    ax.set_ylim(0, 1.02)
    ax.set_yticks([0, .25, .5, .75, 1.0], ["0%", "25%", "50%", "75%", "100%"])
    ax.set_xlabel("Monthly review slots reserved for the new ML scenario (out of 200)")
    ax.set_ylabel("Share of suspicious activity caught")
    ax.set_title("Option C: how many slots should the ML scenario get?", pad=26)
    _subtitle(ax, "Most of the gain comes from the first 20 slots; 60 adds margin while 140 reviews stay with rule alerts")
    _save(fig, "04_ml_slots_sensitivity.png")


def importance(imp: pd.DataFrame):
    d = imp.head(8).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 4.4))
    ax.barh(d.description, d.importance, color=BLUE, height=0.55)
    ax.set_xlabel("Drop in PR-AUC when the feature is shuffled (permutation importance)")
    ax.grid(axis="y", visible=False)
    ax.set_title("What drives the risk score", pad=26)
    _subtitle(ax, "Every top driver is a behaviour an investigator can verify on the account")
    _save(fig, "05_feature_importance.png")


def typology_chart(typ: pd.DataFrame):
    d = typ.copy()
    d["name"] = d.typology.str.replace("_", " ").str.capitalize() + "\n(" + d.cases.astype(str) + " cases)"
    x = range(len(d))
    fig, ax = plt.subplots(figsize=(10, 4.4))
    w = 0.36
    ax.bar([i - w / 2 - 0.01 for i in x], d.rules_all_alerts_reviewed, width=w, color=ORANGE, label="Rules (all alerts reviewed)")
    ax.bar([i + w / 2 + 0.01 for i in x], d.option_C, width=w, color=BLUE, label="Option C (within capacity)")
    for i, (a, b) in enumerate(zip(d.rules_all_alerts_reviewed, d.option_C)):
        ax.text(i - w / 2 - 0.01, a + 0.02, f"{a:.0%}", ha="center", fontsize=9.5, color=TEXT_2)
        ax.text(i + w / 2 + 0.01, b + 0.02, f"{b:.0%}", ha="center", fontsize=9.5, color=TEXT_2)
    ax.set_xticks(list(x), d.name)
    ax.set_ylim(0, 1.15)
    ax.set_yticks([0, .25, .5, .75, 1.0], ["0%", "25%", "50%", "75%", "100%"])
    ax.grid(axis="x", visible=False)
    ax.legend(loc="upper right", ncols=2)
    ax.set_title("Where the gain comes from", pad=26)
    _subtitle(ax, "Small-amount money mules and structurers stay under rule thresholds")
    _save(fig, "06_detection_by_typology.png")


def make_all(results, curve, slots, imp, rule_perf, typ):
    cap = results["assumptions"]["capacity_per_month"]
    rule_alerts(rule_perf, results["rules_test_period"])
    options_chart(results["options"], cap)
    capacity_curve(curve, results["rules_test_period"], results["options"], cap)
    ml_slots(slots)
    importance(imp)
    typology_chart(typ)
