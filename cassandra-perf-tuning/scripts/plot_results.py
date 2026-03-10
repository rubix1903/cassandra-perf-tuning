"""
plot_results.py — Compare baseline vs tuned benchmark results
=============================================================
Usage: python scripts/plot_results.py
Reads results/baseline_*.csv and results/tuned_*.csv and
generates a side-by-side comparison chart.
"""

import os
import glob
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np

RESULTS_DIR = "results"


def load_results(tag: str, op: str) -> dict:
    pattern = os.path.join(RESULTS_DIR, f"{tag}_{op.lower()}_results.csv")
    files = glob.glob(pattern)
    if not files:
        return {}
    df = pd.read_csv(files[0])
    return df.iloc[-1].to_dict()  # latest run


def make_comparison_chart():
    configs = ["baseline", "tuned"]
    ops     = ["WRITE", "READ"]

    fig = plt.figure(figsize=(18, 12), facecolor="#0a0c10")
    fig.suptitle("Cassandra Performance: Baseline vs Tuned",
                 color="#00d4ff", fontsize=16, fontweight="bold", y=0.98)
    gs = gridspec.GridSpec(2, 3, figure=fig, hspace=0.5, wspace=0.4)

    metrics = [
        ("throughput",   "Throughput (ops/sec)", "Higher is better ↑", True),
        ("p95_ms",       "p95 Latency (ms)",     "Lower is better ↓",  False),
        ("p99_ms",       "p99 Latency (ms)",     "Lower is better ↓",  False),
    ]

    colors = {"baseline": "#ff6b35", "tuned": "#00d4ff"}

    for row_idx, op in enumerate(ops):
        for col_idx, (metric_key, metric_label, note, higher_better) in enumerate(metrics):
            ax = fig.add_subplot(gs[row_idx, col_idx])
            ax.set_facecolor("#0f1318")

            vals = {}
            for cfg in configs:
                data = load_results(cfg, op)
                vals[cfg] = float(data.get(metric_key, 0)) if data else 0

            bars = ax.bar(
                list(vals.keys()),
                list(vals.values()),
                color=[colors[c] for c in vals.keys()],
                alpha=0.85,
                width=0.5,
            )

            for bar, val in zip(bars, vals.values()):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + max(vals.values()) * 0.02,
                    f"{val:,.1f}",
                    ha="center", color="#e2ecf4", fontsize=9, fontweight="bold"
                )

            # Delta annotation
            b_val = vals.get("baseline", 0)
            t_val = vals.get("tuned", 0)
            if b_val > 0:
                pct = ((t_val - b_val) / b_val) * 100
                sign = "+" if pct > 0 else ""
                color = "#7fff6b" if (higher_better and pct > 0) or (not higher_better and pct < 0) else "#ff6b35"
                ax.text(0.98, 0.92, f"{sign}{pct:.0f}%",
                        transform=ax.transAxes, ha="right", color=color,
                        fontsize=13, fontweight="bold")

            ax.set_title(f"{op} — {metric_label}", color="#e2ecf4", fontsize=9, pad=8)
            ax.set_xlabel(note, color="#5a7a96", fontsize=8)
            ax.tick_params(colors="#5a7a96")
            for spine in ax.spines.values():
                spine.set_color("#1e2a38")

    out = os.path.join(RESULTS_DIR, "comparison_chart.png")
    plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="#0a0c10")
    print(f"  📊 Comparison chart saved → {out}")


if __name__ == "__main__":
    print("📊 Generating baseline vs tuned comparison charts...\n")
    make_comparison_chart()
