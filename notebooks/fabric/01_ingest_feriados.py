# =====================================================================
# Fabric Notebook: 01_ingest_feriados
# Purpose: fetch Portuguese public holidays and load into dbo.FeriadosPT,
#          then refresh dbo.Dim_Calendario for the relevant year range.
#
# This is the FIRST notebook built in Step 4, deliberately chosen because
# it needs no external secrets (see docs/secrets-strategy-interim.md) —
# it validates the Warehouse connectivity pattern before we build
# notebooks that also need Google Sheets / SharePoint credentials.
#
# CONNECTIVITY: uses notebookutils.data.connect_to_artifact(), the native
# Fabric mechanism available because this notebook was created directly
# from the Warehouse (GestaoDespesasDW already shows up as a OneLake data
# item in the notebook's Explorer panel). No manual token/connection
# string handling needed — see docs/fabric-notebook-connectivity.md.
#
# HOW TO USE:
# Paste each "# CELL n" block below into its own cell in the notebook.
# =====================================================================

# CELL 1 — imports
import requests
import pandas as pd
import notebookutils

WAREHOUSE_NAME = "GestaoDespesasDW"

# CELL 2 — connection helper
def get_warehouse_connection():
    return notebookutils.data.connect_to_artifact(WAREHOUSE_NAME)

# CELL 3 — quick connectivity test (run this first, expect a row count back)
conn = get_warehouse_connection()
result = conn.query("SELECT COUNT(*) AS cnt FROM dbo.FeriadosPT")
print("FeriadosPT current row count:", result["cnt"][0])
print("Connection OK — if you see a row count above (even 0), the connectivity pattern works.")

# CELL 4 — determine the year range to fetch
# Mirrors the legacy etl_master.py's obter_intervalo_anos(): look at the
# min/max year already present across the fact tables, falling back to
# the current year if the warehouse is still empty (as it is right now).
def obter_intervalo_anos():
    conn = get_warehouse_connection()
    query = """
        SELECT MIN(Ano) AS MinAno, MAX(Ano) AS MaxAno FROM (
            SELECT YEAR(Data_Despesa) as Ano FROM dw.Fact_DespesasReais
            UNION
            SELECT YEAR(Data_Despesa) as Ano FROM dw.Fact_Obras
            UNION
            SELECT YEAR(Data_Receita) as Ano FROM dw.Fact_Receitas
            UNION
            SELECT YEAR(Data_Saldo) as Ano FROM dw.Fact_Saldos
            UNION
            SELECT YEAR(Data_Referencia) as Ano FROM dw.Fact_Budget
        ) as Combined
    """
    df = conn.query(query)
    min_year = df["MinAno"][0]
    max_year = df["MaxAno"][0]

    if pd.isna(min_year):
        from datetime import datetime
        min_year = max_year = datetime.now().year
    return int(min_year), int(max_year)

min_year, max_year = obter_intervalo_anos()
print(f"Ano mínimo: {min_year}, Ano máximo: {max_year}")

# CELL 5 — fetch holidays from the public API (unchanged from the legacy script)
todos_feriados = []
for ano in range(min_year, max_year + 1):
    url = f"https://date.nager.at/api/v3/PublicHolidays/{ano}/PT"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            df_fer = pd.DataFrame(resp.json())
            if not df_fer.empty:
                df_temp = pd.DataFrame({"Data": df_fer["date"], "FeriadoNome": df_fer["localName"]})
                todos_feriados.append(df_temp)
                print(f"Feriados {ano}: OK ({len(df_temp)} registos)")
        else:
            print(f"[WARN] API retornou status {resp.status_code} para {ano}")
    except Exception as e:
        print(f"[WARN] Erro ao baixar feriados {ano}: {e}")

df_final = pd.concat(todos_feriados) if todos_feriados else pd.DataFrame(columns=["Data", "FeriadoNome"])
print(f"Total de feriados obtidos: {len(df_final)}")

# CELL 6 — load into dbo.FeriadosPT (truncate + insert)
# .query() takes a raw T-SQL string (no parameter binding confirmed available
# yet for this API), so values are inlined with single-quote escaping —
# safe here because the data comes from a trusted public API, not user input.
conn = get_warehouse_connection()
conn.query("TRUNCATE TABLE dbo.FeriadosPT")

if not df_final.empty:
    values_list = []
    for _, row in df_final.iterrows():
        data_escaped = str(row["Data"]).replace("'", "''")
        nome_escaped = str(row["FeriadoNome"]).replace("'", "''")
        values_list.append(f"('{data_escaped}', '{nome_escaped}')")

    insert_sql = "INSERT INTO dbo.FeriadosPT (Data, FeriadoNome) VALUES " + ", ".join(values_list)
    conn.query(insert_sql)

print(f"{len(df_final)} feriados carregados com sucesso.")

# CELL 7 — refresh the calendar dimension for the same year range
conn = get_warehouse_connection()
conn.query(f"EXEC dbo.sp_AtualizarCalendario @AnoInicio={min_year}, @AnoFim={max_year}")
print("Calendário atualizado com sucesso.")
