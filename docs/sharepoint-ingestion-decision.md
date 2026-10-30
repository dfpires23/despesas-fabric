# SharePoint (Budget) Ingestion Strategy

**Status:** Active.

## Context
The Budget Excel file is hosted on OneDrive for Business (SharePoint-backed). Reading it directly via a Python notebook is impractical because Fabric's `notebookutils` lacks native Microsoft Graph token support, and setting up an Azure AD app introduces unnecessary secret-management overhead for a single file.

## Implemented Solution
The file transfer is decoupled from the Python code:
1. **Pipeline Copy Data Activity:** Uses the native SharePoint connector (authenticated via Organizational account) to extract the `Budget_*.xlsx` file.
2. **Lakehouse Landing Zone:** The file is landed into the `Files` section of a dedicated Lakehouse (`DespesasDEV_Landing`). This Lakehouse acts strictly as a raw file drop zone, maintaining the SQL Warehouse as the core analytical engine.
3. **Notebook Ingestion:** The notebook reads the Excel file directly from the local Fabric mount (`/lakehouse/default/Files/...`) and processes it into the Warehouse.

## Gotchas (cost us debugging time)

- **Source location:** the file lives in the *personal* OneDrive of the dev-tenant admin account (`https://wpnpt-my.sharepoint.com/personal/admin_wpnpt_onmicrosoft_com`), not in a SharePoint team site. The connection must point at that URL.
- **Path must include the `Documents/` prefix:** working path is `Documents/DespesasFamiliares/Input_Budgets`. Without it the Copy activity succeeds but copies nothing (`filesRead: 0`). Check `filesRead` after any path change.

## Risk
The Budget source lives inside the dev tenant (which may be lost, see `local-fallback-runbook.md`), while the legacy system reads its own copy from Google Drive. Two copies exist; the source of truth is still to be decided.