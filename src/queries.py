import sqlite3

import pandas as pd

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

def get_relative_frequencies(
    connection: sqlite3.Connection,
) -> pd.DataFrame:
    """Return cell counts and relative frequencies for every sample."""
    return pd.read_sql_query(
        RELATIVE_FREQUENCY_QUERY,
        connection,
    )