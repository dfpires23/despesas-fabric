# Fabric Notebook ↔ Warehouse Connectivity

**Status:** Active approach.

## Implemented Solution
All Python notebook connections to the Warehouse use the native Fabric API: 
`notebookutils.data.connect_to_artifact("<WarehouseName>")`

This replaces manual `pyodbc` and Azure AD token handling. It requires notebooks to have the Warehouse attached as a data item via the Explorer panel (OneLake data hub), either by creating the notebook from the Warehouse item or via "Add data items". The `.query(sql)` method natively supports `SELECT`, `INSERT`, `UPDATE`, `DELETE`, DDL, and stored procedure execution.

## Known Limitations & Quirks

- **No Parameterized Queries:** The `.query()` API currently only accepts raw T-SQL strings. Standard parameter bindings (e.g., `cursor.execute(sql, params)`) are not supported. 
  *Workaround:* String variables must be manually escaped (e.g., doubling single quotes) before being formatted into the SQL string. This is acceptable here only because the data is trusted (holiday names, expense descriptions from the household's own Form); revisit before reusing with untrusted input.
- **Zero-Row Results Return `None`:** When a non-aggregate `SELECT` query returns zero rows, `.query()` returns a Python `None` type instead of an empty `pandas.DataFrame`. Calling DataFrame methods (like `.empty`) on it will cause an `AttributeError`. Aggregate queries (`COUNT(*)`, `MIN/MAX` without `GROUP BY`) are not affected, which makes the bug easy to miss until a genuinely empty result appears.
  *Rule going forward:* Any notebook calling `.query()` on a non-aggregate SELECT must check `if df is None:` before processing the result.
- **No Persistent Python Libraries:** Fabric's "Environment" feature (which pre-installs and persists libraries) is explicitly for Spark notebooks only. Pure Python notebooks do not retain library installations across sessions.
  *Workaround:* Use inline `%pip install` at the top of the notebook for external packages (like `gspread`). They will reinstall on each pipeline run. Environments become relevant again in Phase 2 with PySpark.