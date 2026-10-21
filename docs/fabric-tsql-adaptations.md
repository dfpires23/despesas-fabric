# Fabric Warehouse T-SQL Adaptations

**Status:** Active reference.  
**Purpose:** Practical record of T-SQL syntax differences and required adaptations discovered during the migration from SQL Server to Fabric Warehouse (each found by running the ported scripts and reading the errors).

## Adaptations Applied

| SQL Server Feature | Fabric Warehouse Adaptation |
|---|---|
| `NVARCHAR` | Not supported. Use `VARCHAR` (UTF-8 collation natively handles Portuguese accents). |
| `PRIMARY KEY` / `FOREIGN KEY` | Cannot be inline (`Msg 24584`). Apply post-creation via `ALTER TABLE ... ADD CONSTRAINT ... NOT ENFORCED`, after all tables exist. |
| `DEFAULT` Constraints | Not supported in any form. Required values (e.g., flags) must be explicitly set in every `INSERT` statement. |
| `IDENTITY` | Must use `BIGINT IDENTITY`; foreign keys referencing these columns must also be `BIGINT`. Custom seeds/increments (e.g., `1,1`) are not supported. |
| `ALTER TABLE ... ADD` | Cannot add `NOT NULL` columns to existing tables (`Msg 24735`); new columns must be added as `NULL`. Combined with no `DEFAULT`, "always populate" columns (e.g., outbox flags) rely entirely on every `INSERT` writing a value: there is no schema-level safety net. |
| Recursive CTEs | Not supported. Logic rewritten using `GENERATE_SERIES(start, stop)`. |
| `CREATE SCHEMA` | Must be alone in its batch and lacks native `IF NOT EXISTS`. Guard via `sys.schemas` check and `EXEC()`. |
| Column Naming | Removed spaces/accents from base tables (to reduce friction for Phase 2 PySpark); display names preserved as aliases in `dbo.vw_*` reporting views. |
| `FORMAT()`, `TRUNCATE`, `CREATE OR ALTER VIEW` | Supported natively without changes. |

## Future Considerations (Phase 2)

- **`MERGE` Statements:** Now generally available in Fabric. Avoided in Phase 1 to maintain legacy `INSERT ... WHERE NOT EXISTS` parity, but is a strong candidate for simplifying ETL logic in Phase 2.
- **Nested CTEs:** Supported but currently flagged as a preview feature. Not required for current workloads. 

*Rule going forward:* Do not assume full SQL Server compatibility for new code; porting is not a copy-paste exercise. Always validate against the Fabric Warehouse T-SQL surface area (e.g., enforce `BIGINT` for surrogates, avoid `DEFAULT`).