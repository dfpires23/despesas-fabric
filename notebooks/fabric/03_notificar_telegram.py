# Fabric Notebook: 03_notificar_telegram
# Outbox notifier (see docs/telegram-notification-design.md): one message per pending row
# (Notificado_Telegram = 0), marked as sent only after Telegram confirms.
# Runs after 02_ingest_despesas. Paste each "# CELL n" block into its own notebook cell.
 
# CELL 1 — dependencies
import requests
import time
import notebookutils
 
WAREHOUSE_NAME = "GestaoDespesasDW"
 
# CELL 2 — parameters cell (toggle "parameter cell" in the Fabric UI)
TELEGRAM_BOT_TOKEN = "<PASTE_YOUR_DEV_BOT_TOKEN_HERE>"
TELEGRAM_CHAT_ID = "<PASTE_YOUR_DEV_CHAT_ID_HERE>"
 
# CELL 3 — connection helper
def get_warehouse_connection():
    return notebookutils.data.connect_to_artifact(WAREHOUSE_NAME)
 
# CELL 4 — fact tables watched by this notebook
TABELAS = [
    {"nome": "dw.Fact_DespesasReais", "id_col": "ID_Despesa", "data_col": "Data_Despesa", "rotulo": "Despesa"},
    {"nome": "dw.Fact_Obras",         "id_col": "ID_Obra",    "data_col": "Data_Despesa", "rotulo": "Obras"},
    {"nome": "dw.Fact_Receitas",      "id_col": "ID_Receita", "data_col": "Data_Receita", "rotulo": "Receita"},
    {"nome": "dw.Fact_Saldos",        "id_col": "ID_Saldo",   "data_col": "Data_Saldo",   "rotulo": "Saldo"},
]
 
# CELL 5 — send pending notifications
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
 
    # query() returns None (not an empty DataFrame) when nothing is pending
    if df_pendentes is None or df_pendentes.empty:
        continue
 
    print(f"{tabela['rotulo']}: {len(df_pendentes)} pending notification(s).")
 
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
                    print(f"[WARN] Failed to send (status {resp.status_code}) for {tabela['id_col']}={row['RowId']} "
                        f"— remains pending and will be retried on the next run.")
        except Exception as e:
                print(f"[WARN] Error sending Telegram notification for {tabela['id_col']}={row['RowId']}: {e}"
                    f" — remains pending and will be retried on the next run.")
 
        time.sleep(1)
 
print(f"Total notifications sent successfully: {total_enviadas}")
 
# CELL 6 — manual resend: set RESEND_CARIMBO to the exact Carimbo_Original, run this cell
# alone, then re-run Cell 5. Leave empty ("") during normal runs.
RESEND_CARIMBO = ""  # e.g. "2026-09-08 10:15:32"
 
if RESEND_CARIMBO:
    conn = get_warehouse_connection()
    carimbo_esc = RESEND_CARIMBO.replace("'", "''")
    for tabela in TABELAS:
        conn.query(
            f"UPDATE {tabela['nome']} SET Notificado_Telegram = 0 "
            f"WHERE Carimbo_Original = '{carimbo_esc}'"
        )
    print(f"Marked for resend: {RESEND_CARIMBO}. Run Cell 5 again to resend it.")
 