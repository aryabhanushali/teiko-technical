from pathlib import Path

import pandas as pd

from src.database import initialize_database, load_dataframe


ROOT_DIR = Path(__file__).resolve().parent
CSV_PATH = ROOT_DIR / "cell-count.csv"
DATABASE_PATH = ROOT_DIR / "cell_counts.db"


def main() -> None:
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"Could not find {CSV_PATH.name} in the project root."
        )

    dataframe = pd.read_csv(CSV_PATH)
    connection = initialize_database(DATABASE_PATH)

    try:
        load_dataframe(connection, dataframe)
    finally:
        connection.close()

    print(f"Loaded {len(dataframe):,} samples.")
    print(f"Created database: {DATABASE_PATH.name}")


if __name__ == "__main__":
    main()