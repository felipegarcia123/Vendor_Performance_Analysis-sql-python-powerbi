"""Build a vendor-brand summary table from the SQLite retail database."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = PROJECT_ROOT / "inventory.db"
LOG_DIR = PROJECT_ROOT / "logs"


def configure_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    logging.basicConfig(filename=LOG_DIR / "get_vendor_summary.log", level=logging.INFO,
                        format="%(asctime)s - %(levelname)s - %(message)s", force=True)
    return logging.getLogger(__name__)


def create_vendor_summary(conn: sqlite3.Connection) -> pd.DataFrame:
    """Return one row per vendor-brand without duplicating purchases or freight.

    Freight is allocated across a vendor's brands in proportion to purchase dollars.
    """
    query = """
    WITH FreightSummary AS (
        SELECT VendorNumber, SUM(Freight) AS VendorFreightCost
        FROM vendor_invoice GROUP BY VendorNumber
    ),
    PriceReference AS (
        SELECT VendorNumber, Brand, MAX(Price) AS ActualPrice, MAX(Volume) AS Volume
        FROM purchase_prices GROUP BY VendorNumber, Brand
    ),
    PurchaseSummary AS (
        SELECT p.VendorNumber, p.VendorName, p.Brand, p.Description, p.PurchasePrice,
               pr.ActualPrice, pr.Volume, SUM(p.Quantity) AS TotalPurchaseQuantity,
               SUM(p.Dollars) AS TotalPurchaseDollars
        FROM purchases AS p
        LEFT JOIN PriceReference AS pr
          ON p.VendorNumber = pr.VendorNumber AND p.Brand = pr.Brand
        WHERE p.PurchasePrice > 0
        GROUP BY p.VendorNumber, p.VendorName, p.Brand, p.Description, p.PurchasePrice,
                 pr.ActualPrice, pr.Volume
    ),
    VendorPurchaseTotals AS (
        SELECT VendorNumber, SUM(TotalPurchaseDollars) AS VendorPurchaseDollars
        FROM PurchaseSummary GROUP BY VendorNumber
    ),
    SalesSummary AS (
        SELECT VendorNo, Brand, SUM(SalesQuantity) AS TotalSalesQuantity,
               SUM(SalesDollars) AS TotalSalesDollars, SUM(ExciseTax) AS TotalExciseTax
        FROM sales GROUP BY VendorNo, Brand
    )
    SELECT ps.VendorNumber, ps.VendorName, ps.Brand, ps.Description, ps.PurchasePrice,
           ps.ActualPrice, ps.Volume, ps.TotalPurchaseQuantity, ps.TotalPurchaseDollars,
           COALESCE(ss.TotalSalesQuantity, 0) AS TotalSalesQuantity,
           COALESCE(ss.TotalSalesDollars, 0) AS TotalSalesDollars,
           COALESCE(ss.TotalExciseTax, 0) AS TotalExciseTax,
           COALESCE(fs.VendorFreightCost * ps.TotalPurchaseDollars /
                    NULLIF(vpt.VendorPurchaseDollars, 0), 0) AS AllocatedFreightCost
    FROM PurchaseSummary AS ps
    JOIN VendorPurchaseTotals AS vpt ON ps.VendorNumber = vpt.VendorNumber
    LEFT JOIN SalesSummary AS ss ON ps.VendorNumber = ss.VendorNo AND ps.Brand = ss.Brand
    LEFT JOIN FreightSummary AS fs ON ps.VendorNumber = fs.VendorNumber
    ORDER BY ps.TotalPurchaseDollars DESC
    """
    return pd.read_sql_query(query, conn)


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Standardize types and add explicitly defined profitability metrics."""
    cleaned = df.copy()
    numeric = ["PurchasePrice", "ActualPrice", "Volume", "TotalPurchaseQuantity",
               "TotalPurchaseDollars", "TotalSalesQuantity", "TotalSalesDollars",
               "TotalExciseTax", "AllocatedFreightCost"]
    for column in numeric:
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce").fillna(0)
    for column in ("VendorName", "Description"):
        cleaned[column] = cleaned[column].fillna("").str.strip()

    cleaned["GrossProfit"] = cleaned["TotalSalesDollars"] - cleaned["TotalPurchaseDollars"]
    cleaned["NetProfitAfterFreight"] = cleaned["GrossProfit"] - cleaned["AllocatedFreightCost"]
    cleaned["ProfitMargin"] = (cleaned["GrossProfit"].div(
        cleaned["TotalSalesDollars"].where(cleaned["TotalSalesDollars"] != 0)) * 100).fillna(0)
    cleaned["StockTurnover"] = cleaned["TotalSalesQuantity"].div(
        cleaned["TotalPurchaseQuantity"].where(cleaned["TotalPurchaseQuantity"] != 0)).fillna(0)
    cleaned["SalesToPurchaseRatio"] = cleaned["TotalSalesDollars"].div(
        cleaned["TotalPurchaseDollars"].where(cleaned["TotalPurchaseDollars"] != 0)).fillna(0)
    return cleaned


def build_vendor_summary(database_path: Path = DATABASE_PATH) -> int:
    logger = configure_logging()
    if not database_path.exists():
        raise FileNotFoundError(f"Database not found: {database_path}. Run ingestion first.")
    with sqlite3.connect(database_path) as conn:
        summary = clean_data(create_vendor_summary(conn))
        summary.to_sql("vendor_sales_summary", conn, if_exists="replace", index=False)
    logger.info("Created vendor_sales_summary with %s rows.", len(summary))
    return len(summary)


if __name__ == "__main__":
    rows = build_vendor_summary()
    print(f"Vendor summary created with {rows:,} rows.")
