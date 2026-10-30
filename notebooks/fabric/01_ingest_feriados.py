# Fabric Notebook: 01_ingest_feriados
# Loads Portuguese public holidays into dbo.FeriadosPT and refreshes dbo.Dim_Calendario.
# Paste each "# CELL n" block into its own notebook cell.
# Warehouse access: see docs/fabric-notebook-connectivity.md.
 
# CELL 1 — imports
import requests
import pandas as pd
import notebookutils
 
WAREHOUSE_NAME = "GestaoDespesasDW"
 
# CELL 2 — connection helper
def get_warehouse_connection():
    return notebookutils.data.connect_to_artifact(WAREHOUSE_NAME)
 
# CELL 3 — connectivity test
conn = get_warehouse_connection()
result = conn.query("SELECT COUNT(*) AS cnt FROM dbo.FeriadosPT")
print("FeriadosPT current row count:", result["cnt"][0])
 
# CELL 4 — year range: min/max year across the fact tables (current year if empty)
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
print(f"Minimum year: {min_year}, Maximum year: {max_year}")
 
# CELL 5 — fetch holidays from the public API
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
                print(f"Holidays {ano}: OK ({len(df_temp)} records)")
        else:
            print(f"[WARN] API returned status {resp.status_code} for {ano}")
    except Exception as e:
        print(f"[WARN] Error downloading holidays for {ano}: {e}")
 
df_final = pd.concat(todos_feriados) if todos_feriados else pd.DataFrame(columns=["Data", "FeriadoNome"])
print(f"Total holidays retrieved: {len(df_final)}")
 
# CELL 6 — load dbo.FeriadosPT (truncate + insert; values escaped manually, trusted public API)
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
 
print(f"{len(df_final)} holidays loaded successfully.")
 
# CELL 7 — refresh the calendar dimension
conn = get_warehouse_connection()
conn.query(f"EXEC dbo.sp_AtualizarCalendario @AnoInicio={min_year}, @AnoFim={max_year}")
print("Calendar updated successfully.")
 