# Data contract

Raw source CSVs are intentionally excluded from version control. Place them in this folder before running the pipeline.

The scripts expect `purchases.csv`, `purchase_prices.csv`, `sales.csv`, and `vendor_invoice.csv`, which become SQLite tables with the same names.

Required columns:

- `purchases`: `VendorNumber`, `VendorName`, `Brand`, `Description`, `PurchasePrice`, `Quantity`, `Dollars`
- `purchase_prices`: `VendorNumber`, `Brand`, `Price`, `Volume`
- `sales`: `VendorNo`, `Brand`, `SalesQuantity`, `SalesDollars`, `ExciseTax`
- `vendor_invoice`: `VendorNumber`, `Freight`
