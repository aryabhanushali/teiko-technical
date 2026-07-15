import sqlite3

import pandas as pd

# the five cell populations, in the order they appear in the csv
CELL_POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]

# The csv is one big flat table, but a subject shows up in lots of rows (one
# per sample per timepoint). I split it into a few tables so the subject-level
# info (condition, sex, response) is only stored once. Counts are stored "long"
# (one row per sample+population) instead of five columns, which makes the
# per-population math in Parts 2-3 easy.
SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE projects (
    project_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name TEXT NOT NULL UNIQUE
);

CREATE TABLE subjects (
    subject_id TEXT PRIMARY KEY,
    project_id INTEGER NOT NULL,
    condition TEXT NOT NULL,
    age INTEGER NOT NULL CHECK (age >= 0),
    sex TEXT NOT NULL CHECK (sex IN ('M', 'F')),
    response TEXT CHECK (response IN ('yes', 'no') OR response IS NULL),
    FOREIGN KEY (project_id) REFERENCES projects(project_id)
);

CREATE TABLE samples (
    sample_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    treatment TEXT NOT NULL,
    sample_type TEXT NOT NULL,
    time_from_treatment_start INTEGER NOT NULL,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id)
);

CREATE TABLE cell_populations (
    population_id INTEGER PRIMARY KEY AUTOINCREMENT,
    population_name TEXT NOT NULL UNIQUE
);

CREATE TABLE cell_counts (
    sample_id TEXT NOT NULL,
    population_id INTEGER NOT NULL,
    count INTEGER NOT NULL CHECK (count >= 0),
    PRIMARY KEY (sample_id, population_id),
    FOREIGN KEY (sample_id) REFERENCES samples(sample_id),
    FOREIGN KEY (population_id) REFERENCES cell_populations(population_id)
);

-- indexes on the columns we filter/group by a lot
CREATE INDEX idx_subjects_project ON subjects(project_id);
CREATE INDEX idx_subjects_condition ON subjects(condition);
CREATE INDEX idx_subjects_response ON subjects(response);
CREATE INDEX idx_samples_subject ON samples(subject_id);
CREATE INDEX idx_samples_treatment ON samples(treatment);
CREATE INDEX idx_samples_type ON samples(sample_type);
CREATE INDEX idx_samples_time ON samples(time_from_treatment_start);
"""


def connect_database(database_path):
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def initialize_database(database_path):
    # start fresh each time so re-running is safe
    if database_path.exists():
        database_path.unlink()
    connection = connect_database(database_path)
    connection.executescript(SCHEMA_SQL)
    return connection


def validate_dataframe(dataframe):
    # basic sanity checks on the csv before we load it
    required_columns = {
        "project", "subject", "condition", "age", "sex", "treatment",
        "response", "sample", "sample_type", "time_from_treatment_start",
        *CELL_POPULATIONS,
    }
    missing = required_columns.difference(dataframe.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

    if dataframe["sample"].isna().any():
        raise ValueError("Sample IDs cannot be missing.")
    if dataframe["subject"].isna().any():
        raise ValueError("Subject IDs cannot be missing.")
    if dataframe["sample"].duplicated().any():
        raise ValueError("Sample IDs must be unique.")

    sexes = set(dataframe["sex"].dropna().unique())
    if not sexes.issubset({"M", "F"}):
        raise ValueError(f"Unexpected sex values: {sorted(sexes)}")

    responses = set(dataframe["response"].dropna().unique())
    if not responses.issubset({"yes", "no"}):
        raise ValueError(f"Unexpected response values: {sorted(responses)}")

    # counts should be non-negative numbers
    for population in CELL_POPULATIONS:
        dataframe[population] = pd.to_numeric(dataframe[population], errors="raise")
        if dataframe[population].isna().any():
            raise ValueError(f"Missing counts found in {population}.")
        if (dataframe[population] < 0).any():
            raise ValueError(f"Negative counts found in {population}.")


def validate_subject_consistency(dataframe):
    # a subject should have the same condition/sex/response etc in every row
    for column in ["project", "condition", "age", "sex", "response"]:
        per_subject = dataframe.groupby("subject")[column].nunique(dropna=True)
        if (per_subject > 1).any():
            raise ValueError(f"Subjects have conflicting values for {column}.")


def load_projects(connection, dataframe):
    projects = sorted(dataframe["project"].unique())
    connection.executemany(
        "INSERT INTO projects (project_name) VALUES (?)",
        [(project,) for project in projects],
    )


def get_project_ids(connection):
    rows = connection.execute("SELECT project_name, project_id FROM projects").fetchall()
    return {name: pid for name, pid in rows}


def load_subjects(connection, dataframe):
    project_ids = get_project_ids(connection)
    # one row per subject
    subjects = dataframe[
        ["subject", "project", "condition", "age", "sex", "response"]
    ].drop_duplicates(subset=["subject"])

    rows = []
    for s in subjects.itertuples(index=False):
        response = None if pd.isna(s.response) else s.response
        rows.append(
            (s.subject, project_ids[s.project], s.condition, int(s.age), s.sex, response)
        )

    connection.executemany(
        """
        INSERT INTO subjects
            (subject_id, project_id, condition, age, sex, response)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def load_samples(connection, dataframe):
    rows = [
        (row.sample, row.subject, row.treatment, row.sample_type,
         int(row.time_from_treatment_start))
        for row in dataframe.itertuples(index=False)
    ]
    connection.executemany(
        """
        INSERT INTO samples
            (sample_id, subject_id, treatment, sample_type, time_from_treatment_start)
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )


def load_populations(connection):
    connection.executemany(
        "INSERT INTO cell_populations (population_name) VALUES (?)",
        [(population,) for population in CELL_POPULATIONS],
    )


def get_population_ids(connection):
    rows = connection.execute(
        "SELECT population_name, population_id FROM cell_populations"
    ).fetchall()
    return {name: pid for name, pid in rows}


def load_cell_counts(connection, dataframe):
    population_ids = get_population_ids(connection)
    # turn the five count columns into one row per sample+population
    rows = []
    for sample in dataframe.itertuples(index=False):
        for population in CELL_POPULATIONS:
            rows.append(
                (sample.sample, population_ids[population], int(getattr(sample, population)))
            )

    connection.executemany(
        "INSERT INTO cell_counts (sample_id, population_id, count) VALUES (?, ?, ?)",
        rows,
    )


def load_dataframe(connection, dataframe):
    dataframe = dataframe.copy()
    validate_dataframe(dataframe)
    validate_subject_consistency(dataframe)
    # `with connection` commits everything together (or rolls back on error)
    with connection:
        load_projects(connection, dataframe)
        load_subjects(connection, dataframe)
        load_samples(connection, dataframe)
        load_populations(connection)
        load_cell_counts(connection, dataframe)
