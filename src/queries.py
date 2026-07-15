import pandas as pd


# Part 2: for each sample, sum the five populations to get the total, then
# express each population's count as a percentage of that total.
RELATIVE_FREQUENCY_QUERY = """
WITH sample_totals AS (
    SELECT
        sample_id,
        SUM(count) AS total_count
    FROM cell_counts
    GROUP BY sample_id
)
SELECT
    cell_counts.sample_id AS sample,
    sample_totals.total_count,
    cell_populations.population_name AS population,
    cell_counts.count,
    ROUND(
        100.0 * cell_counts.count
        / NULLIF(sample_totals.total_count, 0),
        4
    ) AS percentage
FROM cell_counts
JOIN sample_totals
    ON cell_counts.sample_id = sample_totals.sample_id
JOIN cell_populations
    ON cell_counts.population_id = cell_populations.population_id
ORDER BY
    cell_counts.sample_id,
    cell_populations.population_name;
"""


# Same as above but joined with the sample/subject metadata. Parts 3 and 4
# and the dashboard all filter off this one table.
FREQUENCY_WITH_METADATA_QUERY = """
WITH sample_totals AS (
    SELECT
        sample_id,
        SUM(count) AS total_count
    FROM cell_counts
    GROUP BY sample_id
)
SELECT
    samples.sample_id AS sample,
    subjects.subject_id AS subject,
    projects.project_name AS project,
    subjects.condition,
    subjects.sex,
    subjects.response,
    samples.treatment,
    samples.sample_type,
    samples.time_from_treatment_start,
    cell_populations.population_name AS population,
    cell_counts.count,
    sample_totals.total_count,
    ROUND(
        100.0 * cell_counts.count
        / NULLIF(sample_totals.total_count, 0),
        4
    ) AS percentage
FROM cell_counts
JOIN sample_totals
    ON cell_counts.sample_id = sample_totals.sample_id
JOIN samples
    ON cell_counts.sample_id = samples.sample_id
JOIN subjects
    ON samples.subject_id = subjects.subject_id
JOIN projects
    ON subjects.project_id = projects.project_id
JOIN cell_populations
    ON cell_counts.population_id = cell_populations.population_id
ORDER BY
    samples.sample_id,
    cell_populations.population_name;
"""


def get_relative_frequencies(connection):
    # Part 2 summary table: one row per (sample, population).
    return pd.read_sql_query(RELATIVE_FREQUENCY_QUERY, connection)


def get_frequencies_with_metadata(connection):
    return pd.read_sql_query(FREQUENCY_WITH_METADATA_QUERY, connection)
