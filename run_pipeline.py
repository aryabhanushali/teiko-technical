# Runs the analysis (Parts 2-4) and writes all the output tables/figures.
# Expects the database to exist already - run load_data.py first, or just
# use `make pipeline` which does both.

from pathlib import Path
import sqlite3

from src.queries import get_relative_frequencies, get_frequencies_with_metadata
from src.analysis import (
    compare_responders,
    plot_responder_boxplot,
    get_baseline_cohort,
    summarize_baseline,
    average_bcell_melanoma_male_responders,
)

ROOT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = ROOT_DIR / "cell_counts.db"
TABLES_DIR = ROOT_DIR / "outputs" / "tables"
FIGURES_DIR = ROOT_DIR / "outputs" / "figures"


def main():
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            "Database not found. Run `python load_data.py` first."
        )

    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    try:
        frequencies = get_relative_frequencies(connection)
        metadata = get_frequencies_with_metadata(connection)
    finally:
        connection.close()

    # Part 2 - relative frequency summary table
    freq_path = TABLES_DIR / "relative_frequencies.csv"
    frequencies.to_csv(freq_path, index=False)
    print(f"[Part 2] Wrote {len(frequencies):,} rows to {freq_path}")

    # Part 3 - responders vs non-responders
    stats_table = compare_responders(metadata)
    stats_path = TABLES_DIR / "responder_comparison_stats.csv"
    stats_table.to_csv(stats_path, index=False)
    print(f"[Part 3] Wrote statistics to {stats_path}")

    boxplot_path = FIGURES_DIR / "responder_vs_nonresponder_boxplot.png"
    plot_responder_boxplot(metadata, boxplot_path)
    print(f"[Part 3] Wrote boxplot to {boxplot_path}")

    significant = stats_table[stats_table["significant"]]["population"].tolist()
    if significant:
        print(f"[Part 3] Significant populations (p < 0.05): {significant}")
    else:
        print("[Part 3] No populations reached significance.")

    # Part 4 - baseline subset
    baseline = get_baseline_cohort(metadata)
    baseline_path = TABLES_DIR / "baseline_samples.csv"
    baseline.to_csv(baseline_path, index=False)
    print(f"\n[Part 4] {len(baseline)} baseline samples -> {baseline_path}")

    summary = summarize_baseline(baseline)
    print("[Part 4] Samples per project:")
    print(summary["samples_per_project"].to_string())
    print("[Part 4] Subjects by response:")
    print(summary["subjects_by_response"].to_string())
    print("[Part 4] Subjects by sex:")
    print(summary["subjects_by_sex"].to_string())

    avg_bcell = average_bcell_melanoma_male_responders(metadata)
    print(
        "[Part 4] Average B cells for melanoma male responders at time 0 "
        f"(all sample/treatment types): {avg_bcell:.2f}"
    )


if __name__ == "__main__":
    main()
