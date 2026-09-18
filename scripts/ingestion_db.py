"""Load raw retail CSV files into a local SQLite database."""
from __future__ import annotations

import logging
import re
import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = PROJECT_ROOT / "inventory.db"
LOG_DIR = PROJECT_ROOT / "logs"


def configure_logging() -> logging.Logger:
    """Create the log directory before configuring the file handler."""
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(filename=LOG_DIR / "ingestion_db.log", level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s", force=True)
    return logging.getLogger(__name__)


def table_name_from_path(path: Path) -> str:
    """Return a safe SQLite identifier derived from a CSV filename."""
    name = re.sub(r"[^A-Za-z0-9_]", "_", path.stem).strip("_").lower()
    if not name:
        raise ValueError(f"Cannot derive a table name from {path.name!r}.")
    return name


def ingest_dataframe(df: pd.DataFrame, table_name: str, conn: sqlite3.Connection) -> None:
    df.to_sql(table_name, con=conn, if_exists="replace", index=False)


def load_raw_data(data_dir: Path = DATA_DIR, database_path: Path = DATABASE_PATH) -> list[str]:
    """Ingest every CSV in *data_dir* and return the created table names."""
    logger = configure_logging()
    if not data_dir.is_dir():
        raise FileNotFoundError(f"Data directory not found: {data_dir}. Add the required CSV files first.")
    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files were found in {data_dir}.")

    created_tables: list[str] = []
    with sqlite3.connect(database_path) as conn:
        for csv_path in csv_files:
            table_name = table_name_from_path(csv_path)
            df = pd.read_csv(csv_path, low_memory=False)
            ingest_dataframe(df, table_name, conn)
            created_tables.append(table_name)
            logger.info("Ingested %s (%s rows) into %s", csv_path.name, len(df), table_name)
    logger.info("Ingestion complete: %s table(s).", len(created_tables))
    return created_tables


if __name__ == "__main__":
    tables = load_raw_data()
    print(f"Ingestion complete. Created tables: {', '.join(tables)}")
