# =====================================================================
# Fabric Notebook: 02_ingest_despesas
# Purpose: read new expenses from the Google Sheet, load into
#          stg.DespesasReais, and run sp_ProcessarDespesasReais.
#
# SECRETS (see docs/secrets-strategy-interim.md):
#   - Google service account JSON -> uploaded as a Notebook Resource.
#     Right-click the uploaded file in the Explorer -> "Copy relative path"
#     (or similar) and paste that exact value into RESOURCE_PATH below,
#     directly in the Fabric UI. Do NOT hardcode the real path with a
#     credential-bearing filename in a copy of this file kept in Git if
#     that path could reveal anything sensitive (it normally won't, but
#     keep the JSON file itself out of Git regardless).
#
# CONNECTIVITY: uses notebookutils.data.connect_to_artifact(), same
# pattern validated in 01_ingest_feriados. This notebook must also be
# created from (or have added) the GestaoDespesasDW Warehouse as a data
# item, exactly like the Feriados notebook.
#
# HOW TO USE: paste each "# CELL n" block into its own notebook cell.
# =====================================================================

# CELL 1 — dependencies
# %pip install gspread google-auth
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import notebookutils

WAREHOUSE_NAME = "GestaoDespesasDW"
SHEET_DESPESAS = "Despesas_Reais_DB"

# CELL 2 — parameters cell
# In the Fabric UI: select this cell -> cell menu (···) -> "Toggle parameter cell".
# This marks it so a future Pipeline (Step 5) can inject RESOURCE_PATH at
# runtime instead of you typing it by hand every time. For now, fill it
# in manually after uploading credentials.json as a Notebook Resource.
RESOURCE_PATH = "<PASTE_THE_RESOURCE_PATH_TO_credentials.json_HERE>"

# CELL 3 — connection helper (same pattern as 01_ingest_feriados)
def get_warehouse_connection():
    return notebookutils.data.connect_to_artifact(WAREHOUSE_NAME)

# CELL 4 — quick connectivity test
conn = get_warehouse_connection()
result = conn.query("SELECT COUNT(*) AS cnt FROM stg.DespesasReais")
print("stg.DespesasReais current row count:", result["cnt"][0])

# CELL 5 — get already-processed timestamps (Carimbo_Original), across
# all four fact tables — same dedup logic as the legacy etl_master.py
def obter_carimbos_existentes():
    conn = get_warehouse_connection()
    query = """
        SELECT Carimbo_Original FROM dw.Fact_DespesasReais WHERE Carimbo_Original IS NOT NULL
        UNION
        SELECT Carimbo_Original FROM dw.Fact_Obras WHERE Carimbo_Original IS NOT NULL
        UNION
        SELECT Carimbo_Original FROM dw.Fact_Receitas WHERE Carimbo_Original IS NOT NULL
        UNION
        SELECT Carimbo_Original FROM dw.Fact_Saldos WHERE Carimbo_Original IS NOT NULL
    """
    df = conn.query(query)
    # KNOWN FABRIC BEHAVIOR (see docs/fabric-notebook-connectivity.md):
    # conn.query() returns None, not an empty DataFrame, when a non-aggregate
    # query matches zero rows. Any query without GROUP BY/aggregate functions
    # can hit this — must guard for it everywhere, not just here.
    if df is None:
        return []
    return df["Carimbo_Original"].astype(str).tolist() if not df.empty else []

# CELL 6 — extract from Google Sheets
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
creds = Credentials.from_service_account_file(RESOURCE_PATH, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open(SHEET_DESPESAS).sheet1
df = pd.DataFrame(sheet.get_all_records())
print(f"Linhas lidas do Google Sheets: {len(df)}")

# CELL 7 — same column rename/cleanup as the legacy script
df = df.rename(columns={
    df.columns[0]: "Carimbo",
    df.columns[1]: "Data_Despesa",
    df.columns[2]: "Valor",
    df.columns[3]: "Categoria_Full",
    df.columns[4]: "Descricao",
})
df["Carimbo"] = df["Carimbo"].astype(str)

carimbos_existentes = obter_carimbos_existentes()
df_novos = df[~df["Carimbo"].isin(carimbos_existentes)].copy()

df_novos["Data_Despesa"] = pd.to_datetime(df_novos["Data_Despesa"], errors="coerce").dt.strftime("%Y-%m-%d")
df_novos["Valor"] = df_novos["Valor"].replace(r'[€$\s,]', '', regex=True)

print(f"Linhas novas a processar: {len(df_novos)}")

# CELL 8 — load into stg.DespesasReais and run the stored procedure
# (only if there's anything new — mirrors the legacy script's early exit)
if df_novos.empty:
    print("Tudo atualizado. Nenhuma linha nova encontrada.")
else:
    conn = get_warehouse_connection()
    conn.query("TRUNCATE TABLE stg.DespesasReais")

    def esc(v):
        return str(v).replace("'", "''") if pd.notna(v) else ""

    values_list = []
    for _, row in df_novos.iterrows():
        values_list.append(
            f"('{esc(row['Carimbo'])}', '{esc(row['Data_Despesa'])}', "
            f"'{esc(row['Valor'])}', '{esc(row['Categoria_Full'])}', '{esc(row['Descricao'])}')"
        )

    insert_sql = (
        "INSERT INTO stg.DespesasReais (Carimbo, Data_Despesa, Valor, Categoria_Full, Descricao) VALUES "
        + ", ".join(values_list)
    )
    conn.query(insert_sql)
    print(f"{len(df_novos)} linhas carregadas em stg.DespesasReais.")

    conn.query("EXEC dbo.sp_ProcessarDespesasReais")
    print("SP sp_ProcessarDespesasReais executada com sucesso.")
    print("Nota: a notificação Telegram é um passo SEPARADO — corre o notebook "
          "03_notificar_telegram a seguir a este (ver docs/architecture.md secção 5, outbox pattern).")
