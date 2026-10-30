# Power BI Connectivity Strategy

**Status:** Active approach.

## Context
The initial goal was to eliminate the legacy `trigger_pbi_refresh()` block (Service Principal auth, REST API polling, 15-minute timeout loop) that Import-mode Power BI required locally. 

## Implemented Solution
**The semantic model remains in Import mode, but uses native Fabric scheduled refreshes (e.g., 00:00 and 12:00).** Schedule the refresh shortly *after* the pipeline run, otherwise the report can show data up to one interval old.

### Rationale
- **No Orchestration Overhead:** By moving the Warehouse to Fabric, the Power BI semantic model can use native cloud-to-cloud scheduled refreshes. The legacy REST API polling loop and refresh triggers were successfully eliminated.
- **Performance & Simplicity:** Import mode guarantees snappy performance. At the current data volume, the complexities of DirectQuery or Direct Lake are unnecessary.

### Why not Direct Lake (original plan)
Direct Lake was the first choice, to remove refresh entirely. But the model reads the `dbo.vw_*` views, and Direct Lake on SQL endpoints falls back to DirectQuery when the source is a view. Reconnecting to the `dw.*` tables to force true Direct Lake would mean rebuilding in Power BI the joins and column renames the views already provide (they are the stable contract layer). Revisit only if data volume makes latency noticeable (Phase 2 open item).