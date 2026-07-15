# Loblaw Bio - Cell Count Analysis

Analysis of immune cell populations from a clinical trial, for Bob Loblaw at
Loblaw Bio. The project loads `cell-count.csv` into a SQLite database, computes
relative cell-population frequencies, compares treatment responders vs
non-responders, and explores a baseline subset of the data. Results are shown in
an interactive Streamlit dashboard.

**Live dashboard:** https://teiko-technical-ejvtbkq4vp3zxoudnnle93.streamlit.app

## Quick start

```bash
make setup       # install dependencies
make pipeline    # build the database and generate all tables + figures
make dashboard   # launch the interactive dashboard
```

`make setup` installs from `requirements.txt`. `make pipeline` runs
`load_data.py` (Part 1) and then `run_pipeline.py` (Parts 2-4). `make dashboard`
starts Streamlit (default: http://localhost:8501).

You can also run the steps directly:

```bash
python load_data.py        # create cell_counts.db from cell-count.csv
python run_pipeline.py      # write outputs/ tables and figures
python -m pytest            # run the tests
```

## Dashboard

The dashboard is a local Streamlit app. After `make setup`, run
`make dashboard` and open the printed URL (http://localhost:8501). It has three
tabs, one per analysis part:

- **Overview (Part 2)** - relative frequency table, filterable by sample.
- **Responder analysis (Part 3)** - boxplot + statistics for responders vs
  non-responders.
- **Baseline subset (Part 4)** - baseline cohort breakdown and the B-cell metric.

### Hosted deployment

The dashboard builds `cell_counts.db` from `cell-count.csv` on startup if it's
missing, so it runs on a fresh host with no extra setup. To deploy on
[Streamlit Community Cloud](https://share.streamlit.io):

1. Push this repo to GitHub.
2. On Streamlit Cloud, create a new app pointing at this repo, branch `main`,
   main file `dashboard.py`.
3. Streamlit installs `requirements.txt` and serves the app at a public URL.

This repo is deployed at
https://teiko-technical-ejvtbkq4vp3zxoudnnle93.streamlit.app

## Database schema

The CSV is a single flat table, but the same subject appears in many rows (one
per sample per timepoint). To avoid repeating and risking inconsistent subject
data, I split it into five tables:

| Table | Purpose |
|-------|---------|
| `projects` | one row per project (`prj1`, `prj2`, ...) |
| `subjects` | one row per patient: condition, age, sex, response, project |
| `samples` | one row per biological sample: treatment, sample type, time from treatment start |
| `cell_populations` | lookup of the five population names |
| `cell_counts` | the counts - one row per (sample, population) |

**Rationale.** This is a normalized design that mirrors the real hierarchy of
the data: a project has many subjects, a subject has many samples over time, and
each sample has a count for each population. Subject-level facts (sex, condition,
response) live in one place, so they can't disagree between rows. Storing counts
"long" (one row per sample/population) rather than "wide" (five count columns)
means adding a sixth cell population is just new rows, not a schema change, and
it makes the per-population aggregations in Parts 2-3 straightforward SQL.

**Scaling.** With hundreds of projects and thousands of samples this design holds
up well. The tables stay narrow, and the foreign keys plus the indexes (on
project, condition, response, treatment, sample type, and time) keep the typical
filter-and-group-by analytics fast. If the data grew much larger or analysts
wanted heavy cross-sample statistics, the same schema ports directly to Postgres,
and the `cell_counts` table is the natural candidate for partitioning (e.g. by
project) or for a columnar warehouse if the workload became analytics-heavy.

## Code structure

```
load_data.py         # Part 1: create the DB and load the CSV (entry point)
run_pipeline.py      # Parts 2-4: run analysis, write outputs/
dashboard.py         # Streamlit dashboard
src/
  database.py        # schema + loading/validation logic
  queries.py         # SQL that returns the frequency tables
  analysis.py        # statistics (Part 3) and subset analysis (Part 4)
tests/               # pytest tests for the loader and the analysis
outputs/
  tables/            # generated CSVs
  figures/           # generated boxplot
```

I kept the SQL (`queries.py`) separate from the Python analysis (`analysis.py`)
so each is easy to read on its own: the queries just return DataFrames, and the
analysis functions take a DataFrame and filter/summarize it. Both `run_pipeline.py`
and `dashboard.py` reuse those same functions, so the numbers in the dashboard
always match the numbers written to `outputs/`.

## Analysis notes

**Part 2.** For each sample, total count = sum of the five populations, and each
population's percentage = count / total * 100.

**Part 3.** Cohort is melanoma patients on miraclib, PBMC samples only. Each
population's responder vs non-responder frequencies are compared with a
Mann-Whitney U test (non-parametric, so it doesn't assume the percentages are
normally distributed). In this dataset **cd4_t_cell** shows a significant
difference (p ~ 0.013); the others do not. Note: the comparison is done per
sample, following the summary-table instruction - since subjects have repeated
timepoints, a stricter analysis would treat subject as the unit (e.g. average per
subject or a mixed model) to avoid pseudoreplication.

**Part 4.** Baseline = melanoma / miraclib / PBMC samples at
`time_from_treatment_start = 0`. Among those we report samples per project,
subjects by response, and subjects by sex. The final metric - average B-cell
count for melanoma **male responders at time 0** - is computed across *all*
sample and treatment types (not just the baseline cohort), as specified.

## Outputs

Running the pipeline produces:

- `outputs/tables/relative_frequencies.csv` - Part 2 summary table
- `outputs/tables/responder_comparison_stats.csv` - Part 3 statistics
- `outputs/figures/responder_vs_nonresponder_boxplot.png` - Part 3 boxplot
- `outputs/tables/baseline_samples.csv` - Part 4 baseline cohort
