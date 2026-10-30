# Local Fallback Runbook

**Status:** Active. Backports in §2 are **pending** (planned, not yet scheduled).  
**Purpose:** Maintains the legacy system (local SQL Server + Python scripts in `warehouse/legacy/` and `notebooks/legacy/`) as a robust contingency plan if Fabric access is lost (e.g., trial expiration or tenant unavailability). The legacy system also keeps running in production, so every change to it must preserve current behaviour.  
**Context:** Fabric currently runs on a 60-day trial. The planned replacement is a paid, pausable capacity (F2/F4), not trial rotation. The unplanned risk is losing the M365 developer tenant altogether.

---

## 1. Fabric Syntax Exclusions (Do Not Port Back)

The original SQL Server code is structurally superior for its own engine. Do not port back these Fabric-specific workarounds to `warehouse/legacy/`, and never copy the `warehouse/` Fabric scripts (`01_create_schemas_and_tables.sql`, `03_stored_procedures.sql`) over the legacy ones:

| Fabric Adaptation | SQL Server Native Behavior (Keep as-is) |
|---|---|
| `VARCHAR` conversion | Keep `NVARCHAR`. |
| `BIGINT` `IDENTITY` requirement | Keep `INT IDENTITY(1,1)`. |
| `NOT ENFORCED` constraints | Keep inline, enforced `PRIMARY KEY` and `FOREIGN KEY`. |
| No `DEFAULT` support | Keep `DEFAULT` values; they simplify `INSERT` operations. |
| `GENERATE_SERIES` workaround | Keep recursive CTEs (e.g., in `sp_AtualizarCalendario`). |

---

## 2. Required Backports to Legacy Baseline

Apply these improvements to the local system. **Any change to the production SQL Server must be announced and done with the ETL scheduled task disabled.**

| Feature | Action Required | Target File(s) |
|---|---|---|
| **Telegram Outbox Pattern** | Add `Notificado_Telegram` and `Telegram_Message_Id` to each fact table that notifies (see procedure below). | `warehouse/legacy/02_add_outbox_columns.sql`<br>`notebooks/legacy/etl_master.py` |
| **Manual Resend Support** | Reset the outbox flag and rerun the notification step. | `notebooks/legacy/etl_master.py` |
| **Missing-Category Safety Net** | Port the auto-create logic for missing categories from the Fabric procedure. Use `ISNULL(Subcategoria, '')` when concatenating: a `Categoria_Full` without `' - '` yields a NULL subcategory, the concatenation becomes NULL, never matches, and the category would be re-inserted on every run. | `warehouse/legacy/sp_ProcessarDespesasReais.sql` |

### Outbox column migration (order matters)

🚨 Historical rows must end up at `1`, otherwise the first run re-sends the entire expense history to Telegram.

1. Disable the ETL scheduled task.
2. `ALTER TABLE ... ADD Notificado_Telegram BIT NULL, Telegram_Message_Id BIGINT NULL;`
3. `UPDATE ... SET Notificado_Telegram = 1;` (all existing rows were already notified).
4. `ALTER TABLE ... ADD CONSTRAINT DF_... DEFAULT 0 FOR Notificado_Telegram;` (only new rows start pending).
5. Deploy the new `etl_master.py`, run once manually, confirm nothing is re-sent, re-enable the task.

*(Note: The Obras email check and category string matching require no backporting; existing legacy logic suffices.)*

---

## 3. Reactivation Steps (Emergency Cut-over)

If Fabric access is lost, execute these steps to restore local processing:

1. Confirm the `credentials.json` (Google service account) is locally available.
2. Restore the local SQL Server instance and execute all DDL/procedures from `warehouse/legacy/`.
3. Re-enable `RUN_ETL.bat` in Windows Task Scheduler on a reliable machine.
4. Re-point the family-facing `.pbip` Power BI report to the local SQL Server instance.
5. Switch the Telegram bot token back to the production bot/chat.
6. Validate output against the last known-good Fabric state.

---

## 4. Revisit Triggers

- If Phase 2 introduces structural changes to the notification design (e.g., Data Activator).
- If this runbook is ever activated (append an activation log entry with the date and execution notes).