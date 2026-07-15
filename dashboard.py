# Interactive dashboard for the cell-count analysis.
# Run with: streamlit run dashboard.py  (or make dashboard)

from pathlib import Path
import os
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

from src.database import initialize_database, load_dataframe
from src.queries import get_relative_frequencies, get_frequencies_with_metadata
from src.analysis import (
    POPULATIONS,
    get_miraclib_melanoma_pbmc,
    compare_responders,
    get_baseline_cohort,
    summarize_baseline,
    average_bcell_melanoma_male_responders,
)

ROOT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = ROOT_DIR / "cell_counts.db"
CSV_PATH = ROOT_DIR / "cell-count.csv"

# lab palette
TEAL = "#1baf7a"      # responders / accent
RED = "#e34948"       # non-responders
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"
BASELINE = "#c3c2b7"

# clinical / lab styling on top of the base theme in .streamlit/config.toml
LAB_CSS = """
<style>
.block-container { padding-top: 2.2rem; max-width: 1150px; }

/* header */
.lab-title { font-size: 2rem; font-weight: 700; color: #0b0b0b; margin: 0; }
.lab-sub { color: #52514e; font-size: 0.95rem; margin-top: 0.15rem; }
.lab-rule { height: 3px; background: #1baf7a; width: 64px; border-radius: 2px;
            margin: 0.6rem 0 0.2rem 0; }

/* small monospace "lab report" eyebrow above each section */
.eyebrow { font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
           font-size: 0.72rem; letter-spacing: 0.14em; text-transform: uppercase;
           color: #1baf7a; font-weight: 600; }

/* metric cards get a hairline border so they read like readout panels */
[data-testid="stMetric"] {
    background: #fcfcfb;
    border: 1px solid rgba(11,11,11,0.10);
    border-left: 3px solid #1baf7a;
    border-radius: 6px;
    padding: 0.8rem 1rem;
}
[data-testid="stMetricValue"] {
    font-variant-numeric: tabular-nums;
}

/* sample ids / tables in monospace for the instrument feel */
[data-testid="stDataFrame"] { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; }

/* tabs */
.stTabs [data-baseweb="tab"] { font-weight: 600; }
</style>
"""


def eyebrow(text):
    st.markdown(f'<div class="eyebrow">{text}</div>', unsafe_allow_html=True)


def style_axes(ax):
    # recessive grid + axes, matching the marks spec
    ax.set_facecolor(SURFACE)
    ax.figure.set_facecolor(SURFACE)
    for side in ["top", "right"]:
        ax.spines[side].set_visible(False)
    for side in ["left", "bottom"]:
        ax.spines[side].set_color(BASELINE)
    ax.tick_params(colors=MUTED, labelcolor=INK)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def database_has_data():
    if not DATABASE_PATH.exists():
        return False
    try:
        connection = sqlite3.connect(DATABASE_PATH)
        n = connection.execute("SELECT COUNT(*) FROM cell_counts").fetchone()[0]
        connection.close()
        return n > 0
    except sqlite3.Error:
        return False


def ensure_database():
    # Build the db from the csv if we don't already have a populated one.
    # Build into a temp file and swap it in only once it's fully loaded, so an
    # interrupted build never leaves an empty db behind.
    if database_has_data():
        return
    building = DATABASE_PATH.with_name("cell_counts.building.db")
    if building.exists():
        building.unlink()
    dataframe = pd.read_csv(CSV_PATH)
    connection = initialize_database(building)
    try:
        load_dataframe(connection, dataframe)
    finally:
        connection.close()
    os.replace(building, DATABASE_PATH)


@st.cache_data
def load_data():
    # open read-only: the db is committed, and some hosts mount the repo
    # read-only so a normal (read-write) connect could fail.
    connection = sqlite3.connect(f"file:{DATABASE_PATH}?mode=ro", uri=True)
    try:
        frequencies = get_relative_frequencies(connection)
        metadata = get_frequencies_with_metadata(connection)
    finally:
        connection.close()
    return frequencies, metadata


st.set_page_config(page_title="Loblaw Bio Cell Counts", page_icon="🧬", layout="wide")
st.markdown(LAB_CSS, unsafe_allow_html=True)

if not DATABASE_PATH.exists() and not CSV_PATH.exists():
    st.error("Neither the database nor cell-count.csv was found.")
    st.stop()

ensure_database()
frequencies, metadata = load_data()

# header
st.markdown('<div class="lab-title">Loblaw Bio / Immune Cell Populations</div>',
            unsafe_allow_html=True)
st.markdown('<div class="lab-sub">Immunophenotyping readout for the miraclib clinical trial</div>',
            unsafe_allow_html=True)
st.markdown('<div class="lab-rule"></div>', unsafe_allow_html=True)

tab_overview, tab_response, tab_subset = st.tabs(
    ["Overview (Part 2)", "Responder analysis (Part 3)", "Baseline subset (Part 4)"]
)

# Part 2 - relative frequency overview
with tab_overview:
    eyebrow("Part 02 / Cell population frequencies")
    st.subheader("Relative frequency of each cell population")
    st.write(
        "For every sample we sum the five populations and express each "
        "population as a percentage of that total."
    )

    samples = sorted(frequencies["sample"].unique())
    picked = st.multiselect("Filter by sample (leave empty to show all)", samples)
    table = frequencies
    if picked:
        table = frequencies[frequencies["sample"].isin(picked)]

    st.dataframe(table, width="stretch", hide_index=True)
    st.caption(f"{len(table):,} rows")

# Part 3 - responders vs non-responders
with tab_response:
    eyebrow("Part 03 / Response signature")
    st.subheader("Responders vs non-responders")
    st.write(
        "Cohort: **melanoma** patients on **miraclib**, **PBMC** samples only. "
        "Each population is compared with a Mann-Whitney U test."
    )

    cohort = get_miraclib_melanoma_pbmc(metadata)
    stats_table = compare_responders(metadata)

    col_plot, col_stats = st.columns([3, 2])
    with col_plot:
        fig, ax = plt.subplots(figsize=(9, 5))
        sns.boxplot(
            data=cohort,
            x="population",
            y="percentage",
            hue="response",
            hue_order=["yes", "no"],
            order=POPULATIONS,
            palette={"yes": TEAL, "no": RED},
            gap=0.2,
            linewidth=1.1,
            fliersize=2.5,
            ax=ax,
        )
        style_axes(ax)
        ax.set_xlabel("")
        ax.set_ylabel("Relative frequency (%)", color=INK)
        legend = ax.legend(title="Response", frameon=False)
        legend.get_title().set_color(INK)
        st.pyplot(fig)

    with col_stats:
        st.markdown("**Statistics**")
        st.dataframe(stats_table, width="stretch", hide_index=True)

    significant = stats_table[stats_table["significant"]]["population"].tolist()
    if significant:
        st.success("Significant difference (p < 0.05) in: " + ", ".join(significant))
    else:
        st.info("No population reached significance at p < 0.05.")

# Part 4 - baseline subset
with tab_subset:
    eyebrow("Part 04 / Baseline cohort")
    st.subheader("Baseline melanoma / miraclib / PBMC samples (time = 0)")

    baseline = get_baseline_cohort(metadata)
    summary = summarize_baseline(baseline)

    st.metric("Baseline samples", len(baseline))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("**Samples per project**")
        st.dataframe(summary["samples_per_project"].rename("samples"), width="stretch")
    with col2:
        st.markdown("**Subjects by response**")
        st.dataframe(summary["subjects_by_response"].rename("subjects"), width="stretch")
    with col3:
        st.markdown("**Subjects by sex**")
        st.dataframe(summary["subjects_by_sex"].rename("subjects"), width="stretch")

    st.divider()
    avg_bcell = average_bcell_melanoma_male_responders(metadata)
    st.metric(
        "Avg B cells - melanoma male responders at time 0 (all sample & treatment types)",
        f"{avg_bcell:.2f}",
    )

    with st.expander("Show baseline cohort samples"):
        st.dataframe(baseline, width="stretch", hide_index=True)
