# Family Expense Management — Migration to Microsoft Fabric

**Status:** Phase 1 complete. Phase 2 not yet started.  
**Last updated:** 2026-10-21

## 1. Purpose

This document describes the migration of a personal family expense management solution from a PC-dependent architecture (Google Forms → Excel → Python ETL → local SQL Server → Power BI) to Microsoft Fabric.

The project has two goals of equal importance:

1. **Functional**: remove the dependency on a personal PC to run scheduled ETL jobs, and modernize the data platform.
2. **Learning**: use this project as a structured, hands-on way to learn Microsoft Fabric, to be documented and eventually shared as a technical proof-of-concept (POC).

The migration is being executed in three phases:

- **Phase 1 — Foundation** (complete): replicate the current logic on Fabric infrastructure, changing *where* things run, not *how* they work.
- **Phase 2 — Modernization** (tentative scope, not yet committed): candidate directions include PySpark notebooks, a Lakehouse/medallion structure, and event-driven notifications — see §8 for how this will be scoped.
- **Phase 3 — Showcase**: package the project as a public POC/demo.

This document currently covers **Phase 1** in full detail, with Phase 2/3 captured only as a high-level, intentionally open-ended roadmap.


## 2. Current State Architecture (Baseline)

![diagrams/baseline-architecture.svg](diagrams/baseline-architecture.svg)

### 2.1 Components

| Component | Technology | Notes |
|---|---|---|
| Expense capture | Google Forms → Google Sheets | Single sheet, no incremental read (full sheet read every run) |
| Budget input | Excel files on Google Drive (`Budget_YYYY.xlsx`) | Read twice per run (values + a separate "targets" sheet) |
| Orchestration | Windows Task Scheduler → `.bat` → Python | Runs only when the PC is powered on |
| ETL | Python (`etl_master.py`, `obras_report.py`) | Extraction, transformation, load, notifications — all in one monolithic script |
| Staging | SQL Server, schema `stg` | Untyped (mostly `nvarchar`), truncated after each load |
| Data warehouse | SQL Server, schema `dw` | Dimensional model: `Dim_Categoria`, `Dim_Calendario`, `Dim_MetasMensais`, `Fact_DespesasReais`, `Fact_Obras`, `Fact_Receitas`, `Fact_Saldos`, `Fact_Budget` |
| Reporting views | SQL Server, schema `dbo` (`vw_*`) | Stable contract layer consumed by Power BI |
| Deduplication | Business key `Carimbo_Original` (form response timestamp), enforced with `NOT EXISTS` in stored procedures | Effective and idempotent |
| Notifications — Telegram | Bot API, batched in chunks of 20 expenses per message | Sent **before** SQL commit is confirmed |
| Notifications — Obras (renovation) email | SMTP, triggered after SQL load if new "Obras" rows detected | Generates PDF + Excel, saves to Google Drive, sends email |
| BI refresh | Power BI REST API, Service Principal (MSAL), polling loop up to 15 minutes | Only needed because the semantic model is **Import mode** |

### 2.2 Known issues in the current design

| # | Issue | Impact |
|---|---|---|
| 1 | `sp_ProcessarDespesasReais` does not insert new categories into `Dim_Categoria` (only the Budget procedure does) | An expense with an unrecognized category is **silently dropped** — no fact row is inserted, and staging is truncated regardless |
| 2 | Category matching via string concatenation (`Categoria + ' - ' + Subcategoria`) | Fragile to whitespace/accent mismatches between Forms and Budget entries |
| 3 | Icon SVGs hardcoded per category name in `sp_AtualizarIcones` | Presentation logic living in the data layer; new categories silently get no icon |
| 4 | `obras_report.py` writes to a locally-mounted Google Drive path (`G:\...`) | Hard dependency on the PC; blocks the "no PC dependency" objective |
| 5 | No logging, retry, or alerting on failure | Script fails silently to the terminal only |
| 6 | Telegram notification sent **before** SQL commit is confirmed | A failed SQL load after a successful Telegram send results in a "phantom" notification not reflected in the data |
| 7 | Power BI refresh via REST API + Service Principal + 15-minute polling loop | Only required because of Import mode; adds ~90 lines of orchestration code and a hard dependency on Azure AD app registration |
| 8 | Budget files read twice per run from the same source | Redundant I/O, logic split across two functions |

Addressing issues 1, 4, 6, 7, and 8 was part of the Phase 1 migration. Issue 2 (Category matching via string concatenation) remains open as technical debt for Phase 2, alongside items in `data-governance-notes.md` (SCD2, quarantine pattern). The legacy system still has issues 1, 5 and 6; backporting the fixes is tracked in `local-fallback-runbook.md`.


## 3. Migration Objectives

- Eliminate dependency on a personal PC for scheduled ETL execution.
- Explore scheduled ingestion, and later, near real-time/event-driven ingestion.
- Progressively replace the local SQL Server with appropriate Fabric components.
- Continue serving Power BI reliably.
- Learn and apply Microsoft Fabric best practices through this project.
- Establish DEV and PROD environments.
- **Implement version control via GitHub.** Fabric's native Git integration is deferred to Phase 2.
- Explore CI/CD in a later stage — see §8 for the current thinking on GitHub Actions vs. Fabric Deployment Pipelines.
- Eventually turn the project into a technical POC/demo, shareable publicly (LinkedIn), in English.

## 4. Target Architecture — Phase 1

### 4.1 Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Storage engine | **Fabric Warehouse** (not Lakehouse) | Existing stored procedures are pure T-SQL and port with minimal changes. Lakehouse SQL endpoints are read-only and cannot run stored procedures. Lakehouse/Spark is deliberately deferred to Phase 2 to keep Phase 1 focused on infrastructure change, not logic rewrite. |
| Compute for notebooks | **Python (no Spark yet)** | Matches current comfort level; Spark is a Phase 2 learning goal, introduced once the baseline works. |
| Orchestration | **Fabric Pipelines** (not Dataflow Gen2) | Matches existing preference for code-first control; mirrors the current script's step structure but breaks it into independent, resilient activities. |
| Budget file location | **Move from Google Drive to OneDrive for Business** (personal OneDrive of the dev-tenant admin account) | Removes a PC-mounted-drive dependency and an unnecessary external credential set, given the project's Microsoft-centric direction. Note: the file now lives inside the dev tenant; the legacy system still reads its own copy from Google Drive (source of truth to be decided). |
| Expense source | **Keep Google Sheets/Forms permanently** | Tied to Google Forms; there is no plan to migrate away from Forms/Sheets, in this phase or any future one. This is a standing decision, not a deferral. |
| Power BI connectivity | **Import mode** pointed at the Fabric Warehouse SQL endpoint | Goal is to eliminate the legacy REST API polling loop, replacing it with native scheduled refreshes (00:00 and 12:00) against the Fabric Warehouse. |
| Notification reliability | **Outbox pattern** | Guarantees no expense notification is ever permanently lost, regardless of transient failures. |
| Notification granularity | **One Telegram message per expense** (not batched) | Enables deleting/resending a single erroneous entry without affecting others. |
| Environment strategy | **Parallel DEV/UAT for ~1 month**, isolated Telegram bot/chat and Power BI report | Validates the new pipeline without affecting the existing report already used by other family members. |
| Secrets management | **Notebook parameter cells + Notebook Resources** | Key Vault requires an Azure subscription reachable from the Fabric tenant, which isn't currently available. |
| Fabric capacity region | **North Europe** (confirmed at trial activation) | Tenant default region; accepted rather than forcing a different region, per Microsoft's own guidance not to move capacity region without a specific need. |

### 4.2 Target architecture diagram

![diagrams/target-architecture.svg](diagrams/target-architecture.svg)

### 4.3 Structural changes vs. current design

1. **Pipeline-based orchestration** replaces the single monolithic script. Each stage (Budget, Expenses, Telegram, Obras, Holidays/Calendar) is an independent activity. A Telegram failure no longer aborts data loading.
2. **Telegram notification fires only after SQL commit is confirmed**, and uses an outbox pattern so that transient failures never result in permanently lost notifications.  See `telegram-notification-design.md` for details.
3. **Power BI refresh no longer depends on a Service Principal, REST API calls, or a 15-minute polling loop** — replaced by a plain scheduled refresh against the Warehouse endpoint.
4. **Secrets handled via Notebook parameter cells and Notebook Resources**, rather than the legacy `.env` file.
5. **Schedule**: Pipeline trigger every 12 hours in DEV (6 hours planned for PROD — see §5), independent of any personal device being powered on.

## 5. Environment Strategy (DEV/UAT)

To validate the new pipeline without affecting the existing production report (used by other family members), a parallel environment runs for approximately one month:

| Component | DEV/UAT | PROD (current) |
|---|---|---|
| Workspace | `Despesas-DEV` (Fabric) | Local SQL Server (unchanged during validation) |
| Telegram | New bot + private chat (owner only) | Existing bot/chat |
| Power BI | Duplicated `.pbip`, pointed at Fabric Warehouse, published to a test workspace | Existing report, untouched |
| Data source | Google Sheets (same) / Budget from OneDrive | Google Sheets (same) / Budget from Google Drive |

At the end of the validation period, outputs are compared for consistency. Once confidence is established and data matches, Fabric becomes the primary system. The local SQL Server will NOT be decommissioned; it keeps running as a live system and fallback (see `local-fallback-runbook.md`).

### Schedule interval: DEV vs. PROD

During implementation, the DEV pipeline trigger was deliberately set to a **12-hour interval** to reduce noise (notebook runs, notification checks, log volume) during active development. A 6-hour interval remains the target for PROD once the environment is promoted.

## 6. Implementation Plan — Phase 1 (complete)

| Step | Description | Fabric trial required? |
|---|---|---|
| 0 | Repository setup, move Budget files to OneDrive, create DEV Telegram bot/chat, import existing scripts as a versioned baseline | No |
| 1 | Activate Fabric trial, create `Despesas-DEV` workspace, confirm region (North Europe) | Yes |
| 2 | Create Warehouse; recreate `stg` / `dw` / `dbo` schemas, tables, and views | Yes |
| 3 | Port stored procedures | Yes |
| 4 | Build ingestion notebooks (Budget, Expenses, Holidays) and Telegram notification (outbox pattern) | Yes |
| 5 | Build the orchestrating Pipeline (activities, dependencies, scheduled trigger); includes a native Script activity for `Meta_Controlo` | Yes |
| 6 | Duplicate `.pbip`, reconnect to the Warehouse SQL endpoint (Import mode) | Yes |
| 7 | Parallel validation (~1 month), then officially cut-over to Fabric (maintaining legacy as fallback) | Yes |

## 7. Repository Structure

- `docs/` — Architecture documentation and design decisions.
- `notebooks/` — Fabric notebooks (`notebooks/`) and the legacy Python ETL (`notebooks/legacy/`: `etl_master.py`, `obras_report.py`, `RUN_ETL.bat`).
- `pipelines/` — Fabric pipeline definitions.
- `powerbi/` — Power BI reports and project files.
- `tests/` — SQL scripts for data validation.
- `warehouse/` — Fabric Warehouse SQL (schemas, tables, views, stored procedures) and the legacy SQL Server scripts (`warehouse/legacy/`).

## 8. Roadmap Beyond Phase 1 (intentionally high-level and open)

Phase 2's scope is **not yet committed** — the items below are candidate directions raised during Phase 1:

**Phase 2 — Modernization (candidates, to be scoped at kickoff)**

- Migrate Python notebooks to PySpark; introduce Lakehouse and a Bronze/Silver/Gold medallion structure.
- Explore near real-time/event-driven notification via Fabric Data Activator.
- Decide on Import → DirectQuery/Direct Lake for Power BI.
- Enable Fabric's native Git integration against this same GitHub repository (secrets must be moved out of notebook parameter cells first).
- Evaluate **Fabric Deployment Pipelines** for DEV→PROD promotion, optionally complemented by **GitHub Actions** for pre-promotion validation.
- Revisit data quality items (SCD2 for `Dim_Categoria`, quarantine pattern for rejected rows, business key normalization, data contract validation).

**Phase 3 — Showcase**

- Package the project as a public technical POC/demo.
- Translate all remaining materials to English.
- Document architecture decisions and trade-offs for a non-technical/LinkedIn audience.

**Open Decision: Budget Source of Truth**  
Currently, Fabric reads the Budget from OneDrive, while the legacy system reads its own copy from Google Drive. A decision is pending on which file will be the single source of truth moving forward.

## 9. References

- [`telegram-notification-design.md`](telegram-notification-design.md): Telegram Outbox pattern implementation details.
- [`data-governance-notes.md`](data-governance-notes.md): Deferred data modeling and pipeline reliability improvements (SCD2, quarantine patterns).
- [`fabric-tsql-adaptations.md`](fabric-tsql-adaptations.md): T-SQL syntax differences between SQL Server and Fabric Warehouse.
- [`secrets-strategy-interim.md`](secrets-strategy-interim.md): Active approach to credentials management.
- [`fabric-notebook-connectivity.md`](fabric-notebook-connectivity.md): Native `connect_to_artifact` implementation over manual ODBC.
- [`sharepoint-ingestion-decision.md`](sharepoint-ingestion-decision.md): Rationale for Pipeline Copy Data over Graph API.
- [`power-bi-connectivity-decision.md`](power-bi-connectivity-decision.md): Why the semantic model stays in Import mode with native scheduled refresh.
- [`email-delivery-notes.md`](email-delivery-notes.md): SMTP configuration and spam-folder workarounds.
- [`local-fallback-runbook.md`](local-fallback-runbook.md): Legacy system as live fallback, with pending backports and reactivation steps.