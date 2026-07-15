# Makefile for the Loblaw Bio cell-count assignment.
# Targets used by the grader: setup, pipeline, dashboard.

PYTHON ?= python

.PHONY: setup pipeline dashboard test clean

# Install all dependencies.
setup:
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r requirements.txt

# Run the whole pipeline: build the database (Part 1), then run the
# analysis and write all tables/figures (Parts 2-4).
pipeline:
	$(PYTHON) load_data.py
	$(PYTHON) run_pipeline.py

# Start the interactive dashboard.
dashboard:
	$(PYTHON) -m streamlit run dashboard.py

# Run the tests.
test:
	$(PYTHON) -m pytest -q

# Remove generated files.
clean:
	rm -f cell_counts.db
	rm -f outputs/tables/*.csv outputs/figures/*.png
