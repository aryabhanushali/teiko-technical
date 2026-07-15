import pandas as pd

from src.database import initialize_database, load_dataframe
from src.queries import get_relative_frequencies, get_frequencies_with_metadata
from src.analysis import (
    compare_responders,
    get_baseline_cohort,
    average_bcell_melanoma_male_responders,
)


def build_db(tmp_path):
    df = pd.DataFrame({
        "project": ["prj1", "prj1"],
        "subject": ["sbj1", "sbj2"],
        "condition": ["melanoma", "melanoma"],
        "age": [50, 60],
        "sex": ["M", "F"],
        "treatment": ["miraclib", "miraclib"],
        "response": ["yes", "no"],
        "sample": ["s1", "s2"],
        "sample_type": ["PBMC", "PBMC"],
        "time_from_treatment_start": [0, 0],
        "b_cell": [25, 10],
        "cd8_t_cell": [25, 30],
        "cd4_t_cell": [25, 30],
        "nk_cell": [25, 15],
        "monocyte": [0, 15],
    })
    connection = initialize_database(tmp_path / "test.db")
    load_dataframe(connection, df)
    return connection


def test_percentages_sum_to_100(tmp_path):
    connection = build_db(tmp_path)
    freq = get_relative_frequencies(connection)
    totals = freq.groupby("sample")["percentage"].sum()
    for total in totals:
        assert round(total, 2) == 100.0
    connection.close()


def test_compare_responders_shape(tmp_path):
    connection = build_db(tmp_path)
    meta = get_frequencies_with_metadata(connection)
    stats = compare_responders(meta)
    assert len(stats) == 5  # one row per population
    assert "p_value" in stats.columns
    assert "significant" in stats.columns
    connection.close()


def test_baseline_and_bcell_average(tmp_path):
    connection = build_db(tmp_path)
    meta = get_frequencies_with_metadata(connection)

    baseline = get_baseline_cohort(meta)
    assert len(baseline) == 2  # both samples match the baseline filter

    # only sbj1 is a melanoma male responder at t=0, with 25 b cells
    avg = average_bcell_melanoma_male_responders(meta)
    assert avg == 25.0
    connection.close()
