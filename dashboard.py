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


def database_has_data():
    # True only if the db exists and actually has counts loaded.
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
    # Build the db from the csv if we don't already have a populated one, so
    # the app works on a fresh deploy where the .db isn't checked in.
    # We build into a temp file and swap it in only once it's fully loaded,
    # otherwise an interrupted build leaves an empty db behind and every
    # later run reads 0 rows (this is what made the hosted app come up empty).
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


st.set_page_config(page_title="Loblaw Bio Cell Counts", layout="wide")
st.title("Loblaw Bio - Immune Cell Population Dashboard")

if not DATABASE_PATH.exists() and not CSV_PATH.exists():
    st.error("Neither the database nor cell-count.csv was found.")
    st.stop()

ensure_database()
frequencies, metadata = load_data()

tab_overview, tab_response, tab_subset = st.tabs(
    ["Overview (Part 2)", "Responder analysis (Part 3)", "Baseline subset (Part 4)"]
)

# Part 2 - relative frequency overview
with tab_overview:
    st.header("Relative frequency of each cell population")
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
    st.header("Responders vs non-responders")
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
            order=POPULATIONS,
            ax=ax,
        )
        ax.set_xlabel("Cell population")
        ax.set_ylabel("Relative frequency (%)")
        ax.legend(title="Response")
        st.pyplot(fig)

    with col_stats:
        st.subheader("Statistics")
        st.dataframe(stats_table, width="stretch", hide_index=True)

    significant = stats_table[stats_table["significant"]]["population"].tolist()
    if significant:
        st.success("Significant difference (p < 0.05) in: " + ", ".join(significant))
    else:
        st.info("No population reached significance at p < 0.05.")

# Part 4 - baseline subset
with tab_subset:
    st.header("Baseline melanoma / miraclib / PBMC samples (time = 0)")

    baseline = get_baseline_cohort(metadata)
    summary = summarize_baseline(baseline)

    st.metric("Baseline samples", len(baseline))

    col1, col2, col3 = st.columns(3)
    with col1:
        st.subheader("Samples per project")
        st.dataframe(summary["samples_per_project"].rename("samples"), width="stretch")
    with col2:
        st.subheader("Subjects by response")
        st.dataframe(summary["subjects_by_response"].rename("subjects"), width="stretch")
    with col3:
        st.subheader("Subjects by sex")
        st.dataframe(summary["subjects_by_sex"].rename("subjects"), width="stretch")

    st.divider()
    avg_bcell = average_bcell_melanoma_male_responders(metadata)
    st.metric(
        "Avg B cells - melanoma male responders at time 0 (all sample & treatment types)",
        f"{avg_bcell:.2f}",
    )

    with st.expander("Show baseline cohort samples"):
        st.dataframe(baseline, width="stretch", hide_index=True)
