import matplotlib
matplotlib.use("Agg")  # save figures without a display

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from scipy import stats

POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]


def get_miraclib_melanoma_pbmc(frequencies):
    # Part 3 cohort: melanoma patients on miraclib, PBMC samples only.
    # Drop rows with no response since we're comparing responders vs not.
    subset = frequencies[
        (frequencies["condition"] == "melanoma")
        & (frequencies["treatment"] == "miraclib")
        & (frequencies["sample_type"] == "PBMC")
        & (frequencies["response"].isin(["yes", "no"]))
    ]
    return subset.copy()


def compare_responders(frequencies):
    """Mann-Whitney U test of responder vs non-responder frequencies.

    One row per population. I used Mann-Whitney rather than a t-test because
    the percentages aren't necessarily normally distributed.
    """
    cohort = get_miraclib_melanoma_pbmc(frequencies)

    rows = []
    for population in POPULATIONS:
        data = cohort[cohort["population"] == population]
        responders = data[data["response"] == "yes"]["percentage"]
        non_responders = data[data["response"] == "no"]["percentage"]

        if len(responders) == 0 or len(non_responders) == 0:
            p_value = float("nan")
        else:
            _, p_value = stats.mannwhitneyu(
                responders, non_responders, alternative="two-sided"
            )

        rows.append({
            "population": population,
            "n_responders": len(responders),
            "n_non_responders": len(non_responders),
            "median_responder": round(responders.median(), 2),
            "median_non_responder": round(non_responders.median(), 2),
            "p_value": round(p_value, 4),
            "significant": bool(p_value < 0.05),
        })

    result = pd.DataFrame(rows).sort_values("p_value").reset_index(drop=True)
    return result


def plot_responder_boxplot(frequencies, output_path):
    # One grouped boxplot so the responder/non-responder comparison is
    # easy to read for all five populations at once. Teal = responders,
    # red = non-responders, to match the dashboard.
    cohort = get_miraclib_melanoma_pbmc(frequencies)

    teal, red, muted, grid, baseline = "#1baf7a", "#e34948", "#898781", "#e1e0d9", "#c3c2b7"
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.boxplot(
        data=cohort,
        x="population",
        y="percentage",
        hue="response",
        hue_order=["yes", "no"],
        order=POPULATIONS,
        palette={"yes": teal, "no": red},
        gap=0.2,
        linewidth=1.1,
        fliersize=2.5,
        ax=ax,
    )
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(baseline)
    ax.tick_params(colors=muted, labelcolor="#0b0b0b")
    ax.grid(axis="y", color=grid, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title("Cell population frequencies: responders vs non-responders\n"
                 "(melanoma, miraclib, PBMC)")
    ax.set_xlabel("")
    ax.set_ylabel("Relative frequency (%)")
    ax.legend(title="Response", frameon=False)
    plt.tight_layout()
    plt.savefig(output_path, dpi=150)
    plt.close()


# --- Part 4: baseline subset ---

def get_baseline_cohort(frequencies):
    # Melanoma PBMC samples at baseline (time 0) from miraclib patients.
    # The frequency table has 5 rows per sample, so drop the population
    # columns and de-duplicate down to one row per sample.
    subset = frequencies[
        (frequencies["condition"] == "melanoma")
        & (frequencies["treatment"] == "miraclib")
        & (frequencies["sample_type"] == "PBMC")
        & (frequencies["time_from_treatment_start"] == 0)
    ]
    columns = ["sample", "subject", "project", "sex", "response"]
    return subset[columns].drop_duplicates().reset_index(drop=True)


def summarize_baseline(baseline):
    # Samples are counted per project. Responders and sex are counted per
    # subject, so de-duplicate to subjects first.
    subjects = baseline.drop_duplicates(subset=["subject"])
    return {
        "samples_per_project": baseline["project"].value_counts().sort_index(),
        "subjects_by_response": subjects["response"].value_counts(),
        "subjects_by_sex": subjects["sex"].value_counts(),
    }


def average_bcell_melanoma_male_responders(frequencies):
    # Average B-cell count for melanoma male responders at time 0. This one
    # spans ALL sample and treatment types and uses the raw count, not the
    # relative frequency.
    b_cells = frequencies[
        (frequencies["condition"] == "melanoma")
        & (frequencies["sex"] == "M")
        & (frequencies["response"] == "yes")
        & (frequencies["time_from_treatment_start"] == 0)
        & (frequencies["population"] == "b_cell")
    ]
    return round(b_cells["count"].mean(), 2)
