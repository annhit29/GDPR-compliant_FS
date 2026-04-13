"""
Generate overhead decomposition charts from existing benchmark CSVs.

Reads art5&6 and art16_wf1 results to show that the MFOTL enforcer
adds negligible overhead — the LLM (GPT API) is the real bottleneck.

Usage (from instrlib/):
  python -m benchmark.enforcer_vs_llm_charts
"""

import csv
import statistics
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"

SOURCES = {
    "Art 5&6":    RESULTS_DIR / "art5&6_perf_results.csv",
    "Art 16 wf1": RESULTS_DIR / "art16_wf1_perf_results.csv",
}


def _load_totals(csv_path: Path) -> dict[str, list[float]]:
    """Return {mode: [t_total, ...]} from a benchmark CSV."""
    by_mode: dict[str, list[float]] = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            by_mode.setdefault(row["mode"], []).append(float(row["t_total"]))
    return by_mode


def _decompose(by_mode: dict[str, list[float]]) -> tuple[float, float, float]:
    """Return (base_fs, enforcer_overhead, llm_overhead) from mode totals."""
    base = statistics.mean(by_mode["baseline"])
    no_llm = statistics.mean(by_mode["gdpr_no_llm"])
    with_llm = statistics.mean(by_mode["gdpr_with_llm"])
    return base, max(0, no_llm - base), max(0, with_llm - no_llm)


def main():
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib is required: pip install matplotlib")
        return

    labels = []
    bases, enforcers, llms = [], [], []

    for label, csv_path in SOURCES.items():
        if not csv_path.exists():
            print(f"  [SKIP] {csv_path} not found")
            continue
        by_mode = _load_totals(csv_path)
        if not all(m in by_mode for m in ("baseline", "gdpr_no_llm", "gdpr_with_llm")):
            print(f"  [SKIP] {csv_path} missing modes")
            continue
        b, e, l = _decompose(by_mode)
        labels.append(label)
        bases.append(b)
        enforcers.append(e)
        llms.append(l)

    if not labels:
        print("No data to chart.")
        return

    colors = {"base": "#4c78a8", "enforcer": "#f58518", "llm": "#e45756"}

    # ── Chart 1: Per-article stacked bar ──────────────────────────────────
    fig, ax = plt.subplots(figsize=(7, 5))
    x = range(len(labels))
    bars_b = ax.bar(x, bases, label="Base FS", color=colors["base"])
    bars_e = ax.bar(x, enforcers, bottom=bases, label="Enforcer (MFOTL)",
                    color=colors["enforcer"])
    bars_l = ax.bar(x, llms,
                    bottom=[b + e for b, e in zip(bases, enforcers)],
                    label="LLM (GPT API)", color=colors["llm"])

    for bars in (bars_b, bars_e, bars_l):
        for bar in bars:
            h = bar.get_height()
            if h > 0.5:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_y() + h / 2,
                        f"{h:.1f}s", ha="center", va="center",
                        fontsize=9, fontweight="bold", color="white")

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel("Time (s)")
    ax.set_title("Overhead Decomposition by Component")
    ax.legend()
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "enforcer_vs_llm_overhead.png", dpi=150)
    plt.close(fig)
    print(f"  Saved {RESULTS_DIR / 'enforcer_vs_llm_overhead.png'}")

    # ── Chart 2: Aggregated summary bar ───────────────────────────────────
    avg_b = statistics.mean(bases)
    avg_e = statistics.mean(enforcers)
    avg_l = statistics.mean(llms)

    fig, ax = plt.subplots(figsize=(6, 5))
    bar_labels = ["Base FS", "Enforcer\n(MFOTL)", "LLM\n(GPT API)"]
    vals = [avg_b, avg_e, avg_l]
    bar_colors = [colors["base"], colors["enforcer"], colors["llm"]]
    bars = ax.bar(bar_labels, vals, color=bar_colors, width=0.5)

    for bar, val in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f"{val:.2f}s", ha="center", fontsize=11, fontweight="bold")

    ax.set_ylabel("Time (s)")
    ax.set_title("Average Overhead Breakdown (Art 5&6 + Art 16 wf1)")
    fig.tight_layout()
    fig.savefig(RESULTS_DIR / "enforcer_vs_llm_breakdown.png", dpi=150)
    plt.close(fig)
    print(f"  Saved {RESULTS_DIR / 'enforcer_vs_llm_breakdown.png'}")


if __name__ == "__main__":
    main()
