# =====================================================================
# Fabric Notebook: 04_ingest_budget
# Purpose: read the Budget Excel file (landed in this Lakehouse's Files
#          area — see docs/sharepoint-ingestion-decision.md) and load
#          both the budget values (stg.Budget) and the monthly savings
#          targets (dw.Dim_MetasMensais) into the Warehouse.
#
# FIX vs. the legacy script: the file is now read ONCE (not twice) —
# both the pivoted budget values and the "Sheet4" targets are extracted
# from a single pandas.ExcelFile object. See known issue #8 in
# architecture.md.
#
# PREREQUISITE: this notebook must have DespesasDEV_Landing attached as
# its default Lakehouse, and GestaoDespesasDW attached as a Warehouse
# data item (see docs/sharepoint-ingestion-decision.md for why).
#
# HOW TO USE: paste each "# CELL n" block into its own notebook cell.
# =====================================================================

# CELL 1 — imports
import pandas as pd
import notebookutils
import re

WAREHOUSE_NAME = "GestaoDespesasDW"

# CELL 2 — connection helper (same pattern as the other notebooks)
def get_warehouse_connection():
    return notebookutils.data.connect_to_artifact(WAREHOUSE_NAME)

# CELL 3 — quick connectivity test
conn = get_warehouse_connection()
result = conn.query("SELECT COUNT(*) AS cnt FROM stg.Budget")
print("stg.Budget current row count:", result["cnt"][0])

# CELL 4 — list Budget files landed in this Lakehouse (mirrors the legacy
# script's folder scan, adapted to the Lakehouse Files mount point)
import os

FILES_PATH = "/lakehouse/default/Files/Input_Budget"
arquivos = [
    f for f in os.listdir(FILES_PATH)
    if "Budget_" in f and f.endswith(".xlsx") and not f.startswith("~$")
]
print(f"Ficheiros de Budget encontrados: {arquivos}")

# CELL 5 — process each file: single read (openpyxl), extract BOTH the
# pivoted budget values AND the Sheet4 monthly targets from that one read
df_budget_final = pd.DataFrame()
df_metas_final = pd.DataFrame()

for ficheiro in arquivos:
    print(f"Processando ficheiro: {ficheiro}")
    ano = int(ficheiro.replace("Budget_", "").replace(".xlsx", ""))
    caminho = os.path.join(FILES_PATH, ficheiro)

    # Single file handle, reused for both sheets — this is the fix for
    # known issue #8 (the file was read twice in the legacy script)
    xls = pd.ExcelFile(caminho, engine="openpyxl")

    # --- Budget values (first/default sheet) ---
    df = pd.read_excel(xls, sheet_name=0)
    colunas_fixas = ["Categoria", "Subcategoria", "Tipo", "Natureza", "Fonte de Pagamento"]
    cols_meses = [c for c in df.columns if c not in colunas_fixas]

    df_unpivoted = df.melt(
        id_vars=colunas_fixas, value_vars=cols_meses,
        var_name="Mes", value_name="Valor"
    )
    df_unpivoted = df_unpivoted.rename(columns={"Fonte de Pagamento": "Fonte", "Tipo": "Prioridade"})
    df_unpivoted["Ano"] = ano
    df_unpivoted["Valor"] = df_unpivoted["Valor"].fillna(0)
    df_budget_final = pd.concat([df_budget_final, df_unpivoted])

    # --- Monthly targets (Sheet4), from the SAME already-open file ---
    if "Sheet4" in xls.sheet_names:
        df_metas = pd.read_excel(xls, sheet_name="Sheet4")
        df_metas = df_metas.rename(columns={
            "Mês": "Mes", "Poupança": "Pct_Poupanca", "Extras": "Pct_Extras",
        })
        required_cols = ["Mes", "Pct_Poupanca", "Pct_Extras"]
        if all(col in df_metas.columns for col in required_cols):
            df_metas["Ano"] = ano
            df_metas_final = pd.concat([df_metas_final, df_metas])
    else:
        print(f"[WARN] '{ficheiro}' não tem Sheet4 — sem metas para este ano.")

print(f"Total linhas Budget: {len(df_budget_final)}")
print(f"Total linhas Metas: {len(df_metas_final)}")

# CELL 6 — load stg.Budget (truncate + insert)
conn = get_warehouse_connection()
conn.query("TRUNCATE TABLE stg.Budget")

if not df_budget_final.empty:
    def esc(v):
        return str(v).replace("'", "''") if pd.notna(v) else None

    values_list = []
    for _, row in df_budget_final.iterrows():
        categoria = esc(row["Categoria"])
        subcategoria = esc(row["Subcategoria"])
        prioridade = esc(row["Prioridade"])
        natureza = esc(row["Natureza"])
        fonte = esc(row["Fonte"])
        mes = esc(row["Mes"])
        valor = float(row["Valor"]) if pd.notna(row["Valor"]) else 0
        ano = int(row["Ano"])

        def sqlval(v):
            return "NULL" if v is None else f"'{v}'"

        values_list.append(
            f"({sqlval(categoria)}, {sqlval(subcategoria)}, {sqlval(prioridade)}, "
            f"{sqlval(natureza)}, {sqlval(fonte)}, {sqlval(mes)}, {valor}, {ano}, GETDATE())"
        )

    # Batch in chunks of 500 rows per INSERT to keep statements manageable
    CHUNK = 500
    for i in range(0, len(values_list), CHUNK):
        chunk = values_list[i:i + CHUNK]
        insert_sql = (
            "INSERT INTO stg.Budget (Categoria, Subcategoria, Prioridade, Natureza, Fonte, Mes, Valor, Ano, DtCarga) VALUES "
            + ", ".join(chunk)
        )
        conn.query(insert_sql)

    print(f"{len(df_budget_final)} linhas carregadas em stg.Budget.")

# CELL 7 — run sp_ProcessarBudget (moves stg.Budget into dw.Dim_Categoria / dw.Fact_Budget)
conn = get_warehouse_connection()
conn.query("EXEC dbo.sp_ProcessarBudget")
print("SP sp_ProcessarBudget executada com sucesso.")

# CELL 8 — load dw.Dim_MetasMensais (truncate + insert) — kept separate
# from stg.Budget because it's a different grain/target table, same as
# the legacy design; only the source file read was deduplicated (Cell 5)
conn = get_warehouse_connection()
conn.query("TRUNCATE TABLE dw.Dim_MetasMensais")

if not df_metas_final.empty:
    df_metas_final["Mes"] = pd.to_numeric(df_metas_final["Mes"], errors="coerce")
    df_metas_final["Pct_Poupanca"] = pd.to_numeric(df_metas_final["Pct_Poupanca"], errors="coerce").fillna(0)
    df_metas_final["Pct_Extras"] = pd.to_numeric(df_metas_final["Pct_Extras"], errors="coerce").fillna(0)

    values_list = []
    for _, row in df_metas_final.iterrows():
        if pd.isna(row["Mes"]):
            continue
        values_list.append(
            f"({int(row['Ano'])}, {int(row['Mes'])}, {float(row['Pct_Poupanca'])}, {float(row['Pct_Extras'])}, GETDATE())"
        )

    if values_list:
        insert_sql = (
            "INSERT INTO dw.Dim_MetasMensais (Ano, Mes, Pct_Poupanca, Pct_Extras, DtCarga) VALUES "
            + ", ".join(values_list)
        )
        conn.query(insert_sql)
        print(f"{len(values_list)} registos de metas carregados.")
else:
    print("Sem dados de metas para carregar.")
