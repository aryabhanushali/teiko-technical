# Loblaw Bio - Cell Count Analysis

This is my solution for the Teiko technical. It loads `cell-count.csv` into a
SQLite database, computes the relative frequency of each immune cell population,
compares treatment responders vs non-responders, and looks at a baseline subset
of the data. The results are shown in an interactive Streamlit dashboard.

**Live dashboard:** https://teiko-technical-ejvtbkq4vp3zxoudnnle93.streamlit.app

## How to run

The whole thing is driven by the Makefile:

```bash
make setup       # install dependencies from requirements.txt
make pipeline    # build the database and generate all tables + figures
make dashboard   # start the interactive dashboard
```

- `make pipeline` runs `load_data.py` (Part 1, builds `cell_counts.db`) and then
  `run_pipeline.py` (Parts 2-4, writes everything under `outputs/`).
- `make dashboard` starts Streamlit, by default at http://localhost:8501.

You can also run the steps by hand:

```bash
python load_data.py        # Part 1: create cell_counts.db from cell-count.csv
python run_pipeline.py     # Parts 2-4: write outputs/ tables and figures
python -m pytest           # run the tests
```

## Dashboard

The dashboard has three tabs, one per analysis part:

- **Overview (Part 2)** - the relative frequency table, filterable by sample.
- **Responder analysis (Part 3)** - the responders-vs-non-responders boxplot next
  to the statistics table.
- **Baseline subset (Part 4)** - the baseline cohort counts and the B-cell metric.

I gave it a clinical "lab report" look (teal = responders, red = non-responders).

**Deployment.** The app is on Streamlit Community Cloud (link above). The built
database `cell_counts.db` is committed so the hosted app has data immediately;
if it's ever missing, the app rebuilds it from `cell-count.csv` on startup, so it
also works on a completely fresh checkout. To deploy your own copy: push to
GitHub, then on [Streamlit Cloud](https://share.streamlit.io) create an app
pointing at the repo, branch `main`, main file `dashboard.py`.

## Database schema

The CSV is one flat table, but the same subject shows up in many rows (one per
sample per timepoint). To avoid repeating subject info everywhere (and risking it
disagreeing between rows), I split it into five tables:

| Table | Purpose |
|-------|---------|
| `projects` | one row per project (`prj1`, `prj2`, ...) |
| `subjects` | one row per patient: condition, age, sex, response, project |
| `samples` | one row per sample: treatment, sample type, time from treatment start |
| `cell_populations` | lookup of the five population names |
| `cell_counts` | the counts, one row per (sample, population) |

**Why this design.** It mirrors the real relationships of the data: a project has
many subjects, a subject has many samples over time, and each sample has a count
for each population. Subject-level facts (sex, condition, response) are stored
once, so they can't contradict each other. Storing the counts "long" (one row per
sample/population) instead of "wide" (five count columns) means the per-population
math in Parts 2-3 is simple SQL, and adding a sixth population later would just be
more rows, not a schema change.

**How it scales.** With hundreds of projects and thousands of samples this holds
up fine. The tables stay narrow, and the foreign keys plus the indexes (on
project, condition, response, treatment, sample type, and time) keep the usual
filter-and-group-by queries fast. If the data got much bigger, the same schema
moves straight to a server database like Postgres, and `cell_counts` is the
obvious table to partition (e.g. by project) or move into a columnar warehouse
if the work became heavily analytical. Because analytics read from the queries in
`src/queries.py`, adding a new analysis is writing one more query, not reshaping
the data.

## Code structure

```
load_data.py         # Part 1: create the DB and load the CSV (entry point)
run_pipeline.py      # Parts 2-4: run the analysis, write outputs/
dashboard.py         # Streamlit dashboard
src/
  database.py        # schema + loading/validation
  queries.py         # the SQL that returns the frequency tables
  analysis.py        # statistics (Part 3) and subset analysis (Part 4)
tests/               # pytest tests for the loader and the analysis
outputs/
  tables/            # generated CSVs
  figures/           # generated boxplot
```

I split the SQL (`queries.py`) from the Python analysis (`analysis.py`) so each is
easy to follow on its own: the queries just return DataFrames, and the analysis
functions take a DataFrame and filter/summarize it. Both `run_pipeline.py` and
`dashboard.py` call the same functions, so the numbers on the dashboard always
match the CSVs written to `outputs/`.

## Analysis notes

**Part 2.** For each sample, total = sum of the five populations, and each
population's percentage = count / total * 100.

**Part 3.** Cohort is melanoma patients on miraclib, PBMC samples only. For each
population I compare responders vs non-responders with a Mann-Whitney U test
(non-parametric, so I don't have to assume the percentages are normally
distributed). In this data **cd4_t_cell** comes out significant (p ~ 0.013) and
the others don't. One caveat: I compare per sample, following the summary-table
instruction. Since subjects have repeated timepoints, a stricter analysis would
use the subject as the unit (average per subject, or a mixed model) to avoid
pseudoreplication.

**Part 4.** Baseline = melanoma / miraclib / PBMC samples at
`time_from_treatment_start = 0`. For those I report samples per project, subjects
by response, and subjects by sex. The last metric - average B-cell count for
melanoma male responders at time 0 - is taken across *all* sample and treatment
types (not just the baseline cohort), as the question specifies.

## Outputs

`make pipeline` produces:

- `outputs/tables/relative_frequencies.csv` - Part 2 summary table
- `outputs/tables/responder_comparison_stats.csv` - Part 3 statistics
- `outputs/figures/responder_vs_nonresponder_boxplot.png` - Part 3 boxplot
- `outputs/tables/baseline_samples.csv` - Part 4 baseline cohort
