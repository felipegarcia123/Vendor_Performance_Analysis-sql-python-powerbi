"""Regression tests for summary-table aggregation rules."""
import sqlite3

import pandas as pd

from scripts.get_vendor_summary import clean_data, create_vendor_summary


def test_summary_matches_price_by_vendor_and_allocates_freight() -> None:
    """A shared brand must not duplicate purchases across price-list vendors."""
    with sqlite3.connect(":memory:") as conn:
        pd.DataFrame([
            {"VendorNumber": 1, "VendorName": "Vendor A", "Brand": 10,
             "Description": "Product", "PurchasePrice": 5.0, "Quantity": 10, "Dollars": 50.0},
            {"VendorNumber": 1, "VendorName": "Vendor A", "Brand": 11,
             "Description": "Product B", "PurchasePrice": 10.0, "Quantity": 5, "Dollars": 50.0},
        ]).to_sql("purchases", conn, index=False)
        pd.DataFrame([
            {"VendorNumber": 1, "Brand": 10, "Price": 9.0, "Volume": 12},
            {"VendorNumber": 1, "Brand": 11, "Price": 15.0, "Volume": 6},
            {"VendorNumber": 2, "Brand": 10, "Price": 99.0, "Volume": 1},
        ]).to_sql("purchase_prices", conn, index=False)
        pd.DataFrame([
            {"VendorNo": 1, "Brand": 10, "SalesQuantity": 8, "SalesDollars": 80.0, "ExciseTax": 0.0},
        ]).to_sql("sales", conn, index=False)
        pd.DataFrame([{"VendorNumber": 1, "Freight": 20.0}]).to_sql("vendor_invoice", conn, index=False)

        summary = clean_data(create_vendor_summary(conn))

    assert len(summary) == 2
    assert summary["TotalPurchaseDollars"].sum() == 100.0
    assert summary["AllocatedFreightCost"].sum() == 20.0
    assert summary.loc[summary["Brand"] == 10, "ActualPrice"].iloc[0] == 9.0
