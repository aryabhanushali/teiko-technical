from pathlib import Path
import sqlite3

import pandas as pd


CELL_POPULATIONS = [
    "b_cell",
    "cd8_t_cell",
    "cd4_t_cell",
    "nk_cell",
    "monocyte",
]


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
    response TEXT CHECK (
        response IN ('yes', 'no') OR response IS NULL
    ),
    FOREIGN KEY (project_id)
        REFERENCES projects(project_id)
);

CREATE TABLE samples (
    sample_id TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    treatment TEXT NOT NULL,
    sample_type TEXT NOT NULL,
    time_from_treatment_start INTEGER NOT NULL,
    FOREIGN KEY (subject_id)
        REFERENCES subjects(subject_id)
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
    FOREIGN KEY (sample_id)
        REFERENCES samples(sample_id),
    FOREIGN KEY (population_id)
        REFERENCES cell_populations(population_id)
);

CREATE INDEX idx_subjects_project
ON subjects(project_id);

CREATE INDEX idx_subjects_condition
ON subjects(condition);

CREATE INDEX idx_subjects_response
ON subjects(response);

CREATE INDEX idx_samples_subject
ON samples(subject_id);

CREATE INDEX idx_samples_treatment
ON samples(treatment);

CREATE INDEX idx_samples_type
ON samples(sample_type);

CREATE INDEX idx_samples_time
ON samples(time_from_treatment_start);
"""


def connect_database(database_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def validate_dataframe(dataframe: pd.DataFrame) -> None:
    required_columns = {
        "project",
        "subject",
        "condition",
        "age",
        "sex",
        "treatment",
        "response",
        "sample",
        "sample_type",
        "time_from_treatment_start",
        *CELL_POPULATIONS,
    }

    missing_columns = required_columns.difference(dataframe.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    if dataframe["sample"].isna().any():
        raise ValueError("Sample IDs cannot be missing.")

    if dataframe["subject"].isna().any():
        raise ValueError("Subject IDs cannot be missing.")

    if dataframe["sample"].duplicated().any():
        raise ValueError("Sample IDs must be unique.")

    observed_sexes = set(dataframe["sex"].dropna().unique())

    if not observed_sexes.issubset({"M", "F"}):
        raise ValueError(
            f"Unexpected sex values: {sorted(observed_sexes)}"
        )

    observed_responses = set(
        dataframe["response"].dropna().unique()
    )

    if not observed_responses.issubset({"yes", "no"}):
        raise ValueError(
            "Unexpected response values: "
            f"{sorted(observed_responses)}"
        )

    for population in CELL_POPULATIONS:
        dataframe[population] = pd.to_numeric(
            dataframe[population],
            errors="raise",
        )

        if dataframe[population].isna().any():
            raise ValueError(
                f"Missing counts found in {population}."
            )

        if (dataframe[population] < 0).any():
            raise ValueError(
                f"Negative counts found in {population}."
            )


def validate_subject_consistency(
    dataframe: pd.DataFrame,
) -> None:
    subject_columns = [
        "project",
        "condition",
        "age",
        "sex",
        "response",
    ]

    for column in subject_columns:
        values_per_subject = (
            dataframe.groupby("subject")[column]
            .nunique(dropna=True)
        )

        if (values_per_subject > 1).any():
            raise ValueError(
                f"Subjects have conflicting values for {column}."
            )


def initialize_database(
    database_path: Path,
) -> sqlite3.Connection:
    if database_path.exists():
        database_path.unlink()

    connection = connect_database(database_path)
    connection.executescript(SCHEMA_SQL)

    return connection


def load_projects(
    connection: sqlite3.Connection,
    dataframe: pd.DataFrame,
) -> None:
    projects = sorted(dataframe["project"].unique())

    connection.executemany(
        """
        INSERT INTO projects (project_name)
        VALUES (?)
        """,
        [(project,) for project in projects],
    )


def get_project_ids(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT project_name, project_id
        FROM projects
        """
    ).fetchall()

    return {
        project_name: project_id
        for project_name, project_id in rows
    }


def load_subjects(
    connection: sqlite3.Connection,
    dataframe: pd.DataFrame,
) -> None:
    project_ids = get_project_ids(connection)

    subjects = dataframe[
        [
            "subject",
            "project",
            "condition",
            "age",
            "sex",
            "response",
        ]
    ].drop_duplicates(subset=["subject"])

    rows = []

    for subject in subjects.itertuples(index=False):
        response = (
            None
            if pd.isna(subject.response)
            else subject.response
        )

        rows.append(
            (
                subject.subject,
                project_ids[subject.project],
                subject.condition,
                int(subject.age),
                subject.sex,
                response,
            )
        )

    connection.executemany(
        """
        INSERT INTO subjects (
            subject_id,
            project_id,
            condition,
            age,
            sex,
            response
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


def load_samples(
    connection: sqlite3.Connection,
    dataframe: pd.DataFrame,
) -> None:
    rows = [
        (
            row.sample,
            row.subject,
            row.treatment,
            row.sample_type,
            int(row.time_from_treatment_start),
        )
        for row in dataframe.itertuples(index=False)
    ]

    connection.executemany(
        """
        INSERT INTO samples (
            sample_id,
            subject_id,
            treatment,
            sample_type,
            time_from_treatment_start
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        rows,
    )


def load_populations(
    connection: sqlite3.Connection,
) -> None:
    connection.executemany(
        """
        INSERT INTO cell_populations (population_name)
        VALUES (?)
        """,
        [(population,) for population in CELL_POPULATIONS],
    )


def get_population_ids(
    connection: sqlite3.Connection,
) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT population_name, population_id
        FROM cell_populations
        """
    ).fetchall()

    return {
        population_name: population_id
        for population_name, population_id in rows
    }


def load_cell_counts(
    connection: sqlite3.Connection,
    dataframe: pd.DataFrame,
) -> None:
    population_ids = get_population_ids(connection)
    rows = []

    for sample in dataframe.itertuples(index=False):
        for population in CELL_POPULATIONS:
            rows.append(
                (
                    sample.sample,
                    population_ids[population],
                    int(getattr(sample, population)),
                )
            )

    connection.executemany(
        """
        INSERT INTO cell_counts (
            sample_id,
            population_id,
            count
        )
        VALUES (?, ?, ?)
        """,
        rows,
    )


def load_dataframe(
    connection: sqlite3.Connection,
    dataframe: pd.DataFrame,
) -> None:
    dataframe = dataframe.copy()

    validate_dataframe(dataframe)
    validate_subject_consistency(dataframe)

    with connection:
        load_projects(connection, dataframe)
        load_subjects(connection, dataframe)
        load_samples(connection, dataframe)
        load_populations(connection)
        load_cell_counts(connection, dataframe)