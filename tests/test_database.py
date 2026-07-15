import pandas as pd
import pytest

from src.database import (
    initialize_database,
    load_dataframe,
    validate_dataframe,
)


def make_sample_dataframe():
    # tiny two-row dataset we can check by hand
    return pd.DataFrame({
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
        "b_cell": [10, 20],
        "cd8_t_cell": [10, 20],
        "cd4_t_cell": [10, 20],
        "nk_cell": [10, 20],
        "monocyte": [10, 20],
    })


def test_load_creates_all_rows(tmp_path):
    connection = initialize_database(tmp_path / "test.db")
    load_dataframe(connection, make_sample_dataframe())

    # 2 samples x 5 populations = 10 count rows
    count = connection.execute("SELECT COUNT(*) FROM cell_counts").fetchone()[0]
    assert count == 10

    subjects = connection.execute("SELECT COUNT(*) FROM subjects").fetchone()[0]
    assert subjects == 2
    connection.close()


def test_negative_count_rejected():
    bad = make_sample_dataframe()
    bad.loc[0, "b_cell"] = -5
    with pytest.raises(ValueError):
        validate_dataframe(bad)


def test_duplicate_sample_rejected():
    bad = make_sample_dataframe()
    bad.loc[1, "sample"] = "s1"
    with pytest.raises(ValueError):
        validate_dataframe(bad)
