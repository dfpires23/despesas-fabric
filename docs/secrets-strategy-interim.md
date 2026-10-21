# Secrets Strategy

**Status:** Active approach.

## Context
The original plan to use Azure Key Vault was deferred because it requires an Azure subscription in the same Microsoft Entra tenant. A native Fabric workaround is currently used.

### Alternatives ruled out
1. **Moving a personal Azure for Students subscription into the Fabric tenant:** blocked. Azure for Students subscriptions cannot be transferred between tenants.
2. **Fabric Variable Library as a secret store:** it has no "secret" variable type, and its values are only reachable by a notebook when a pipeline passes them in as a parameter.

## Implemented Approach

| Secret type | Storage Location | Retrieval Method |
|---|---|---|
| **String secrets** (Telegram tokens, SMTP credentials) | **Notebook Parameter Cells** | Stored directly in the parameter cells of the Fabric Notebooks (the pipeline passes no secret parameters). |
| **JSON files** (Google service account credentials) | **Notebook Resource** (Fabric's built-in file attachment) | Read from the local resource path at runtime. |

### Security Posture & Phase 2 Risk

- ✅ **Workspace isolation:** Access is governed by Fabric workspace permissions.
- ❌ **No granular secret RBAC:** Anyone with workspace edit access can view notebook parameters and attached resources. Acceptable for a single-person/family project only.
- ❌ **No rotation, versioning or audit log** (Key Vault would provide these).
- 🚨 **CRITICAL RISK FOR PHASE 2 (Git Integration):** **When Fabric's native Git integration is enabled, the parameter cells will be committed to the repository in plain text.** A new secret approach MUST be in place before enabling it. Key Vault is the natural target but needs a usable Azure subscription in the same tenant (see ruled-out paths above).