# Fabric Notebook: 02_ingest_despesas
# Reads new expenses from the Google Sheet, loads stg.DespesasReais, and runs sp_ProcessarDespesasReais.
# Paste each "# CELL n" block into its own notebook cell.
# Google credentials: upload the service-account JSON as a Notebook Resource (see docs/secrets-strategy-interim.md).
# Telegram is a separate notebook (03_notificar_telegram).
 
# CELL 1 — dependencies
# %pip install gspread google-auth
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import notebookutils
 
WAREHOUSE_NAME = "GestaoDespesasDW"
SHEET_DESPESAS = "Despesas_Reais_DB"
 
# CELL 2 — parameters cell (toggle "parameter cell" in the Fabric UI)
RESOURCE_PATH = "<PASTE_THE_RESOURCE_PATH_TO_credentials.json_HERE>"
 
# CELL 3 — connection helper
def get_warehouse_connection():
    return notebookutils.data.connect_to_artifact(WAREHOUSE_NAME)
 
# CELL 4 — connectivity test
conn = get_warehouse_connection()
result = conn.query("SELECT COUNT(*) AS cnt FROM stg.DespesasReais")
print("Current stg.DespesasReais row count:", result["cnt"][0])
 
# CELL 5 — timestamps (Carimbo_Original) already loaded across the four fact tables
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
    # query() returns None (not an empty DataFrame) when no rows match
    if df is None:
        return []
    return df["Carimbo_Original"].astype(str).tolist() if not df.empty else []
 
# CELL 6 — read the Google Sheet
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
creds = Credentials.from_service_account_file(RESOURCE_PATH, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open(SHEET_DESPESAS).sheet1
df = pd.DataFrame(sheet.get_all_records())
print(f"Rows read from Google Sheets: {len(df)}")
 
# CELL 7 — rename columns (positional) and keep only new rows
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
 
print(f"New rows to process: {len(df_novos)}")
 
# CELL 8 — load stg.DespesasReais and run the stored procedure
if df_novos.empty:
    print("Everything is up to date. No new rows found.")
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
    print(f"{len(df_novos)} rows loaded into stg.DespesasReais.")
 
    conn.query("EXEC dbo.sp_ProcessarDespesasReais")
    print("SP sp_ProcessarDespesasReais executed successfully.")
 