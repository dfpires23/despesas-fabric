# Data Governance & Modeling Notes

**Status:** Active backlog.  
**Purpose:** Tracks data modeling decisions and pipeline reliability improvements acknowledged in Phase 1 but explicitly deferred to Phase 2. "Confirmed" items are decisions already taken; "Gap" items are acknowledged but undecided in design. None is implemented yet.

## Planned Improvements (Phase 2)

| # | Topic | Type | Current State (Phase 1) | Target State (Phase 2) |
|---|---|---|---|---|
| **1** | **Single Source of Truth (Categories)** | Confirmed principle | Category taxonomies are maintained independently in both Budget Excel and Google Forms. | Budget Excel (`Dim_Categoria`) becomes the sole authoritative source; Google Form dropdowns are auto-generated from it (e.g., via Apps Script). |
| **2** | **Data Contract Validation** | Gap | Sheets ingestion reads columns positionally, risking silent failures if the form schema changes. | Validate incoming columns by explicit name against an expected schema; fail loudly if validation fails. |
| **3** | **Quarantine Pattern** | Gap | Unparseable dates/amounts (`TRY_CAST` → NULL) and malformed rows are silently discarded during staging. (Unrecognized categories are handled in Fabric by the missing-category safety net; the legacy system still drops them.) | Route rejected rows to a quarantine table (e.g., `stg.Rejeitados`) with the explicit failure reason. |
| **4** | **SCD2 for `Dim_Categoria`** | Confirmed direction | Category attribute updates overwrite existing records (implicit SCD1, a side effect of `sp_ProcessarBudget`, not a decision). | Implement SCD2 with effective dating (`ValidFrom`, `ValidTo`, `IsCurrent`) and resolve the category valid at transaction date in fact joins, to report history with the classification in force at the time. |
| **5** | **Row-Count Reconciliation** | Gap | No observability verifying that rows extracted match rows loaded into the warehouse. | Log row counts at each pipeline stage and flag/alert on discrepancies. |
| **6** | **Business Key Normalization** | Gap | Category matching relies on exact string concatenation, which is fragile to whitespace/accents. | Apply `TRIM` and consistent case normalization during the matching process. |

## Process note: Meta_Controlo (fixed)

When the monolithic legacy `etl_master.py` was split into Fabric notebooks, the final step `atualizar_meta_controlo()` (one row in `dw.Meta_Controlo` with the current timestamp, used by Power BI for "last updated") was never ported: no notebook clearly owned it. It was fixed with a native Pipeline **Script** activity as the last step, triggered `On Completion` (not `On Success`) so the timestamp updates even if a notification step had nothing to do.

**Lesson:** decomposing a monolith trades one risk for another. A single script cannot forget a step it contains, but separate notebooks can leave a step without an owner. Check the pipeline against the legacy step list after any split.