# =====================================================================
# Fabric Notebook: 03_notificar_telegram
# Purpose: outbox-pattern Telegram notifier (see docs/architecture.md,
#          section 5). Runs AFTER 02_ingest_despesas has committed to the
#          Warehouse — never before, and never as part of the same step.
#
# Sends ONE Telegram message per expense (not batched), stores the
# returned message_id, and only marks a row as notified after a
# confirmed successful send. Any row left at Notificado_Telegram = 0
# (because it was never processed, or the send failed) is automatically
# picked up again next time this notebook runs — including for the
# manual resend workflow (reset Notificado_Telegram = 0 for a specific
# Carimbo_Original, then re-run this notebook).
#
# SECRETS (see docs/secrets-strategy-interim.md): TELEGRAM_BOT_TOKEN and
# TELEGRAM_CHAT_ID are filled in directly in the Fabric UI parameters
# cell for now — never committed with real values.
#
# HOW TO USE: paste each "# CELL n" block into its own notebook cell.
# =====================================================================

# CELL 1 — dependencies
import requests
import time
import notebookutils

WAREHOUSE_NAME = "GestaoDespesasDW"

# CELL 2 — parameters cell
# Toggle this as a "parameter cell" in the Fabric UI (cell menu -> Toggle
# parameter cell), same as RESOURCE_PATH in 02_ingest_despesas. Fill in
# manually for now; the Pipeline (Step 5) will inject these later.
TELEGRAM_BOT_TOKEN = "<PASTE_YOUR_DEV_BOT_TOKEN_HERE>"
TELEGRAM_CHAT_ID = "<PASTE_YOUR_DEV_CHAT_ID_HERE>"

# CELL 3 — connection helper (same pattern as the other notebooks)
def get_warehouse_connection():
    return notebookutils.data.connect_to_artifact(WAREHOUSE_NAME)

# CELL 4 — the four fact tables this notebook watches, with the columns
# needed to build a message and to update the row back afterward.
# (id_col, table, date_col, extra table-specific label used in the message)
TABELAS = [
    {"nome": "dw.Fact_DespesasReais", "id_col": "ID_Despesa", "data_col": "Data_Despesa", "rotulo": "Despesa"},
    {"nome": "dw.Fact_Obras",         "id_col": "ID_Obra",    "data_col": "Data_Despesa", "rotulo": "Obras"},
    {"nome": "dw.Fact_Receitas",      "id_col": "ID_Receita", "data_col": "Data_Receita", "rotulo": "Receita"},
    {"nome": "dw.Fact_Saldos",        "id_col": "ID_Saldo",   "data_col": "Data_Saldo",   "rotulo": "Saldo"},
]

# CELL 5 — send Telegram notifications for every pending row, across all
# four fact tables, one message per expense.
conn = get_warehouse_connection()
total_enviadas = 0

for tabela in TABELAS:
    query = f"""
        SELECT F.{tabela['id_col']} AS RowId,
               F.{tabela['data_col']} AS Data,
               F.Valor,
               F.Descricao,
               C.Categoria,
               C.Subcategoria
        FROM {tabela['nome']} AS F
        LEFT JOIN dw.Dim_Categoria AS C ON F.ID_Categoria = C.ID_Categoria
        WHERE F.Notificado_Telegram = 0
    """
    df_pendentes = conn.query(query)

    # KNOWN FABRIC BEHAVIOR (see docs/fabric-notebook-connectivity.md):
    # conn.query() returns None, not an empty DataFrame, when a non-aggregate
    # query matches zero rows — very likely here whenever nothing is pending.
    if df_pendentes is None:
        continue

    if df_pendentes.empty:
        continue

    print(f"{tabela['rotulo']}: {len(df_pendentes)} notificação(ões) pendente(s).")

    for _, row in df_pendentes.iterrows():
        categoria_txt = f"{row['Categoria']} - {row['Subcategoria']}" if row['Categoria'] else tabela['rotulo']
        valor_formatado = f"{float(row['Valor']):,.2f} €" if row['Valor'] is not None else "N/D"
        mensagem = (
            f"✅ <b>{tabela['rotulo']}</b>\n\n"
            f"{row['Data']}, {categoria_txt}\n"
            f"{valor_formatado}, {row['Descricao'] or ''}"
        )

        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": mensagem, "parse_mode": "HTML"}

        try:
            resp = requests.post(url, data=payload, timeout=10)
            if resp.status_code == 200:
                message_id = resp.json()["result"]["message_id"]
                update_sql = (
                    f"UPDATE {tabela['nome']} "
                    f"SET Notificado_Telegram = 1, Telegram_Message_Id = {message_id} "
                    f"WHERE {tabela['id_col']} = {int(row['RowId'])}"
                )
                conn.query(update_sql)
                total_enviadas += 1
            else:
                print(f"[WARN] Falha ao enviar (status {resp.status_code}) para {tabela['id_col']}={row['RowId']} "
                      f"— fica pendente, será retentado na próxima execução.")
        except Exception as e:
            print(f"[WARN] Erro ao enviar Telegram para {tabela['id_col']}={row['RowId']}: {e}"
                  f" — fica pendente, será retentado na próxima execução.")

        time.sleep(1)  # gentle rate limiting, same spirit as the legacy script

print(f"Total de notificações enviadas com sucesso: {total_enviadas}")

# CELL 6 — manual resend helper (run this cell by itself, with the two
# variables filled in, whenever you need to resend one specific expense —
# e.g. after deleting the Telegram message and correcting a value).
# Leave RESEND_CARIMBO empty ("") to skip this cell during normal runs.
RESEND_CARIMBO = ""  # e.g. "2026-09-08 10:15:32" — the exact Carimbo_Original value

if RESEND_CARIMBO:
    conn = get_warehouse_connection()
    carimbo_esc = RESEND_CARIMBO.replace("'", "''")
    for tabela in TABELAS:
        conn.query(
            f"UPDATE {tabela['nome']} SET Notificado_Telegram = 0 "
            f"WHERE Carimbo_Original = '{carimbo_esc}'"
        )
    print(f"Marcado para reenvio: {RESEND_CARIMBO}. Corre a Cell 5 novamente para o reenviar.")
