from pathlib import Path
import sqlite3

from src.queries import get_relative_frequencies
ROOT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = ROOT_DIR/"cell_counts.db"
TABLES_DIR = ROOT_DIR/"outputs"/"tables"
def main() -> None:
    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            "Database not found. Run `python load_data.py` first."
        )
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(DATABASE_PATH)
    try:
        relative_frequencies = get_relative_frequencies(connection)
    finally:
        connection.close()

    output_path = TABLES_DIR / "relative_frequencies.csv"

    relative_frequencies.to_csv(
        output_path,
        index=False,
    )
    print(
        f"Saved {len(relative_frequencies):,} rows "
        f"to {output_path}"
    )
if __name__ == "__main__":
    main()