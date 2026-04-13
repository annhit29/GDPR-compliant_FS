"""
Generate comparison charts for the README.

Charts produced:
  1. overhead_decomposition.png — Stacked bars: Base FS vs Enforcer vs LLM for all articles with 3 modes
  2. art16_side_by_side.png    — Art 16 wf1 (has write->LLM) vs wf2 (no write->no LLM), per-step
  3. art5_6_per_step_log.png   — Art 5&6 per-step with log scale (baseline visible)
  4. art16_wf1_per_step_log.png — Art 16 wf1 per-step with log scale
  5-12. artX_combined.png      — Per-step + Total side-by-side for each workflow

Usage (from instrlib/):
  python -m benchmark.comparison_charts
"""

import csv
import statistics
from pathlib import Path
import numpy as np

RESULTS_DIR = Path(__file__).resolve().parent / "results"

MODE_COLORS = {"baseline": "#4c78a8", "gdpr_no_llm": "#f58518", "gdpr_with_llm": "#e45756"}


def _load_csv(csv_path: Path) -> list[dict]:
    with open(csv_path) as f:
        return list(csv.DictReader(f))


def _mode_totals(rows: list[dict]) -> dict[str, float]:
    by_mode: dict[str, list[float]] = {}
    for r in rows:
        by_mode.setdefault(r["mode"], []).append(float(r["t_total"]))
    return {m: statistics.mean(v) for m, v in by_mode.items()}


def _step_means(rows: list[dict], mode: str) -> dict[str, float]:
    mode_rows = [r for r in rows if r["mode"] == mode]
    if not mode_rows:
        return {}
    step_cols = [c for c in mode_rows[0].keys()
                 if c.startswith("t_") and c != "t_total"
                 and c not in ("mode", "iteration")]
    result = {}
    for col in step_cols:
        vals = [float(r[col]) for r in mode_rows]
        result[col.removeprefix("t_")] = statistics.mean(vals)
    return result


# ═══════════════════════════════════════════════════════════════════════════
# Chart 1: Overhead Decomposition (all articles with 3 modes)
# ═══════════════════════════════════════════════════════════════════════════

def chart_overhead_decomposition():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sources = {
        "Art 5&6":     RESULTS_DIR / "art5&6_perf_results.csv",
        "Art 16\nwf1":  RESULTS_DIR / "art16_wf1_perf_results.csv",
        "Art 16\nwf2":  RESULTS_DIR / "art16_wf2_perf_results.csv",
    }

    labels, bases, enforcers, llms = [], [], [], []

    for label, path in sources.items():
        if not path.exists():
            print(f"  [SKIP] {path}")
            continue
        totals = _mode_totals(_load_csv(path))
        if not all(m in totals for m in ("baseline", "gdpr_no_llm", "gdpr_with_llm")):
            print(f"  [SKIP] {path} missing modes")
            continue
        b = totals["baseline"]
        e = max(0, totals["gdpr_no_llm"] - b)
        l = max(0, totals["gdpr_with_llm"] - totals["gdpr_no_llm"])
        labels.append(label)
        bases.append(b)
        enforcers.append(e)
        llms.append(l)

    if not labels:
        print("No data for overhead decomposition.")
        return

    colors = {"base": "#4c78a8", "enforcer": "#f58518", "llm": "#e45756"}

    fig, ax = plt.subplots(figsize=(8, 5.5))
    x = np.arange(len(labels))
    width = 0.5

    bars_b = ax.bar(x, bases, width, label="Base FS", color=colors["base"])
    bars_e = ax.bar(x, enforcers, width, bottom=bases,
                    label="Enforcer (MFOTL)", color=colors["enforcer"])
    bars_l = ax.bar(x, llms, width,
                    bottom=[b + e for b, e in zip(bases, enforcers)],
                    label="LLM (GPT API)", color=colors["llm"])

    # Annotate values inside large bars (LLM)
    for bars in (bars_b, bars_e, bars_l):
        for j, bar in enumerate(bars):
            h = bar.get_height()
            if h > 3:
                ax.text(bar.get_x() + bar.get_width() / 2,
                        bar.get_y() + h / 2,
                        f"{h:.1f}s", ha="center", va="center",
                        fontsize=10, fontweight="bold", color="white")

    # Annotate thin enforcer bars with staggered heights to avoid overlap
    enforcer_stagger = {0: 18, 1: 8}  # group index → y-offset for label
    for j, bar in enumerate(bars_e):
        h = bar.get_height()
        total_for_group = bases[j] + enforcers[j] + llms[j]
        if h > 0.001 and total_for_group > 3:
            y_target = enforcer_stagger.get(j, 10)
            ax.annotate(f"Enforcer: {h:.1f}s",
                        xy=(bar.get_x() + bar.get_width() / 2, bar.get_y() + h),
                        xytext=(bar.get_x() + bar.get_width() / 2 + 0.15, y_target),
                        fontsize=9, fontweight="bold", color="#333333",
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="white", edgecolor="#f58518", alpha=0.9),
                        arrowprops=dict(arrowstyle="->", color="#f58518", lw=1.2),
                        ha="left", va="bottom")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=11)
    ax.set_ylabel("Time (s)", fontsize=12)
    ax.set_title("Overhead Decomposition: Enforcer vs LLM", fontsize=13, fontweight="bold")
    ax.legend(fontsize=10, loc="upper right", bbox_to_anchor=(1.0, 1.0),
              framealpha=0.9)

    # Add annotation for wf2: show actual values since bars are too small to see
    wf2_idx = labels.index("Art 16\nwf2") if "Art 16\nwf2" in labels else None
    if wf2_idx is not None:
        wf2_b = bases[wf2_idx]
        wf2_e = enforcers[wf2_idx]
        wf2_l = llms[wf2_idx]
        wf2_total = wf2_b + wf2_e + wf2_l
        ax.annotate(
            f"No write step in this workflow,\n"
            f"so LLM is never triggered.\n"
            f"Total: {wf2_total:.2f}s\n"
            f"(Base {wf2_b:.4f}s + Enforcer {wf2_e:.2f}s + LLM {wf2_l:.2f}s)",
            xy=(wf2_idx, wf2_total + 0.3),
            xytext=(wf2_idx - 0.3, max(llms) * 0.25),
            ha="center", fontsize=8.5, fontstyle="italic", color="#333",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#f0f0f0", edgecolor="#aaa", alpha=0.9),
            arrowprops=dict(arrowstyle="->", color="#888", lw=1.2),
        )

    fig.tight_layout()
    out = RESULTS_DIR / "overhead_decomposition.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Saved {out}")


# ═══════════════════════════════════════════════════════════════════════════
# Chart 2: Art 16 wf1 vs wf2 side-by-side per-step
# ═══════════════════════════════════════════════════════════════════════════

def chart_art16_side_by_side():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    wf1_path = RESULTS_DIR / "art16_wf1_perf_results.csv"
    wf2_path = RESULTS_DIR / "art16_wf2_perf_results.csv"
    if not wf1_path.exists() or not wf2_path.exists():
        print("  [SKIP] Art 16 CSVs not found")
        return

    wf1_rows = _load_csv(wf1_path)
    wf2_rows = _load_csv(wf2_path)

    modes = ["baseline", "gdpr_no_llm", "gdpr_with_llm"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5.5))

    for ax, rows, title in [
        (ax1, wf1_rows, "wf1: Write New Data + Read\n(has write -> triggers LLM)"),
        (ax2, wf2_rows, "wf2: Rectify Pre-existing Data + Read\n(no write -> no LLM call)"),
    ]:
        all_steps = {m: _step_means(rows, m) for m in modes}
        step_names = list(all_steps[modes[0]].keys()) if all_steps[modes[0]] else []
        if not step_names:
            continue

        x = np.arange(len(step_names))
        n_modes = len(modes)
        bar_width = 0.8 / n_modes

        for i, m in enumerate(modes):
            vals = [max(all_steps[m].get(s, 0), 1e-7) for s in step_names]
            ax.bar(x + i * bar_width - 0.4 + bar_width / 2, vals, bar_width,
                   label=m, color=MODE_COLORS[m])

        ax.set_xticks(x)
        ax.set_xticklabels(step_names, rotation=35, ha="right", fontsize=9)
        ax.set_ylabel("Time (s)")
        ax.set_title(title, fontsize=11, fontweight="bold")
        ax.legend(fontsize=8, loc="upper left")
        ax.set_yscale("log")
        ax.set_ylim(bottom=1e-5)
        ax.grid(axis="y", alpha=0.3)

    fig.suptitle("Art 16: Per-Step Latency Comparison (log scale)",
                 fontsize=13, fontweight="bold", y=1.02)
    fig.tight_layout()
    out = RESULTS_DIR / "art16_side_by_side.png"
    fig.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved {out}")


# ═══════════════════════════════════════════════════════════════════════════
# Chart 3: Art 5&6 per-step with log scale
# ═══════════════════════════════════════════════════════════════════════════

def chart_art5_6_per_step_log():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    csv_path = RESULTS_DIR / "art5&6_perf_results.csv"
    if not csv_path.exists():
        print("  [SKIP] Art 5&6 CSV not found")
        return

    rows = _load_csv(csv_path)
    modes = ["baseline", "gdpr_no_llm", "gdpr_with_llm"]

    all_steps = {m: _step_means(rows, m) for m in modes}
    step_names = list(all_steps[modes[0]].keys())

    fig, ax = plt.subplots(figsize=(14, 5.5))
    x = np.arange(len(step_names))
    n_modes = len(modes)
    bar_width = 0.8 / n_modes

    for i, m in enumerate(modes):
        vals = [max(all_steps[m].get(s, 0), 1e-7) for s in step_names]
        ax.bar(x + i * bar_width - 0.4 + bar_width / 2, vals, bar_width,
               label=m, color=MODE_COLORS[m])

    ax.set_xticks(x)
    ax.set_xticklabels(step_names, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Time (s)")
    ax.set_title("Art 5&6 Collect Workflow -- Per-Step Latency (log scale)\n"
                 "Log scale reveals baseline and enforcer times hidden by the LLM bars",
                 fontsize=12, fontweight="bold")
    ax.set_yscale("log")
    ax.set_ylim(bottom=1e-7)
    ax.legend(fontsize=10, loc="upper left")
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    out = RESULTS_DIR / "art5_6_per_step_log.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Saved {out}")


# ═══════════════════════════════════════════════════════════════════════════
# Chart 4: Art 16 wf1 per-step with log scale
# ═══════════════════════════════════════════════════════════════════════════

def chart_art16_wf1_per_step_log():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    csv_path = RESULTS_DIR / "art16_wf1_perf_results.csv"
    if not csv_path.exists():
        print("  [SKIP] Art 16 wf1 CSV not found")
        return

    rows = _load_csv(csv_path)
    modes = ["baseline", "gdpr_no_llm", "gdpr_with_llm"]

    all_steps = {m: _step_means(rows, m) for m in modes}
    step_names = list(all_steps[modes[0]].keys())

    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = np.arange(len(step_names))
    n_modes = len(modes)
    bar_width = 0.8 / n_modes

    for i, m in enumerate(modes):
        vals = [max(all_steps[m].get(s, 0), 1e-7) for s in step_names]
        ax.bar(x + i * bar_width - 0.4 + bar_width / 2, vals, bar_width,
               label=m, color=MODE_COLORS[m])

    ax.set_xticks(x)
    ax.set_xticklabels(step_names, rotation=35, ha="right", fontsize=9)
    ax.set_ylabel("Time (s)")
    ax.set_title("Art 16 wf1 (Write New Data + Read) -- Per-Step Latency (log scale)\n"
                 "Only the write step shows LLM overhead; all other steps are enforcer-only",
                 fontsize=12, fontweight="bold")
    ax.set_yscale("log")
    ax.set_ylim(bottom=1e-7)
    ax.legend(fontsize=10, loc="upper left")
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    out = RESULTS_DIR / "art16_wf1_per_step_log.png"
    fig.savefig(out, dpi=150)
    plt.close(fig)
    print(f"  Saved {out}")


# ═══════════════════════════════════════════════════════════════════════════
# Charts 5-12: Combined per-step + total side-by-side for each workflow
# ═══════════════════════════════════════════════════════════════════════════

WORKFLOW_CSVS = {
    "art5&6":    ("Art 5&6 Collect Workflow",                RESULTS_DIR / "art5&6_perf_results.csv"),
    "art9":      ("Art 9 Special Categories Workflow",       RESULTS_DIR / "art9_perf_results.csv"),
    "art15_wf1": ("Art 15 Right of Access (wf1)",            RESULTS_DIR / "art15_wf1_perf_results.csv"),
    "art15_wf2": ("Art 15 Right of Access (wf2)",            RESULTS_DIR / "art15_wf2_perf_results.csv"),
    "art16_wf1": ("Art 16 Right to Rectification (wf1)",     RESULTS_DIR / "art16_wf1_perf_results.csv"),
    "art16_wf2": ("Art 16 Right to Rectification (wf2)",     RESULTS_DIR / "art16_wf2_perf_results.csv"),
    "art17":     ("Art 17 Right to Erasure",                 RESULTS_DIR / "art17_perf_results.csv"),
    "art30":     ("Art 30 Records of Processing",            RESULTS_DIR / "art30_perf_results.csv"),
}


def chart_combined_per_workflow():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    for key, (title, csv_path) in WORKFLOW_CSVS.items():
        if not csv_path.exists():
            print(f"  [SKIP] {csv_path}")
            continue

        rows = _load_csv(csv_path)
        modes = sorted(set(r["mode"] for r in rows),
                       key=lambda m: ["baseline", "gdpr_no_llm", "gdpr_with_llm"].index(m)
                       if m in ["baseline", "gdpr_no_llm", "gdpr_with_llm"] else 99)

        # --- Left: per-step ---
        all_steps = {m: _step_means(rows, m) for m in modes}
        step_names = list(all_steps[modes[0]].keys()) if all_steps[modes[0]] else []
        if not step_names:
            print(f"  [SKIP] {key}: no step data")
            continue

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 5),
                                        gridspec_kw={"width_ratios": [3, 1]})

        x = np.arange(len(step_names))
        n_modes = len(modes)
        bar_width = 0.8 / n_modes

        for i, m in enumerate(modes):
            color = MODE_COLORS.get(m, "#999999")
            vals = [all_steps[m].get(s, 0) for s in step_names]
            ax1.bar(x + i * bar_width - 0.4 + bar_width / 2, vals, bar_width,
                    label=m, color=color)

        ax1.set_xticks(x)
        ax1.set_xticklabels(step_names, rotation=35, ha="right", fontsize=9)
        ax1.set_ylabel("Time (s)")
        ax1.set_title("Per-Step Latency", fontsize=11, fontweight="bold")
        ax1.legend(fontsize=8, loc="upper left")

        # --- Right: total ---
        totals = []
        for m in modes:
            mode_rows = [r for r in rows if r["mode"] == m]
            totals.append(statistics.mean([float(r["t_total"]) for r in mode_rows]))

        colors = [MODE_COLORS.get(m, "#999999") for m in modes]
        bars = ax2.bar(modes, totals, color=colors, width=0.5)

        for bar, val in zip(bars, totals):
            ax2.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max(totals) * 0.02,
                     f"{val:.2f}s", ha="center", fontsize=9, fontweight="bold")

        ax2.set_ylabel("Time (s)")
        ax2.set_title("Total Latency", fontsize=11, fontweight="bold")
        ax2.set_xticks(range(len(modes)))
        ax2.set_xticklabels(modes, rotation=20, ha="right", fontsize=9)

        fig.suptitle(title, fontsize=13, fontweight="bold", y=1.02)
        fig.tight_layout()
        out = RESULTS_DIR / f"{key}_combined.png"
        fig.savefig(out, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"  Saved {out}")


def main():
    print("Generating comparison charts...")
    chart_overhead_decomposition()
    chart_art16_side_by_side()
    chart_art5_6_per_step_log()
    chart_art16_wf1_per_step_log()
    chart_combined_per_workflow()
    print("Done.")


if __name__ == "__main__":
    main()
