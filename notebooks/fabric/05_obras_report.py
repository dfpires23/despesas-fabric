# =====================================================================
# Fabric Notebook: 05_obras_report
# Purpose: generate a PDF summary of "Obras" (home renovation) expenses
#          and email it — adapted from the legacy obras_report.py.
#
# Changes vs. the legacy script:
#   - No longer writes to a locally-mounted Google Drive path (G:\...).
#     The PDF is saved to this Lakehouse's Files area instead
#     (DespesasDEV_Landing/Files/Output_Obras/), which is reachable from
#     anywhere, not just a specific PC.
#   - Excel report dropped entirely (per decision) — PDF only.
#   - SMTP credentials handled via a parameters cell (see
#     docs/secrets-strategy-interim.md), not a .env file.
#   - Uses notebookutils.data.connect_to_artifact() for the Warehouse
#     query, same pattern as the other Step 4 notebooks.
#
# PREREQUISITE: same as 04_ingest_budget — DespesasDEV_Landing attached
# as default Lakehouse, GestaoDespesasDW attached as Warehouse data item.
#
# HOW TO USE: paste each "# CELL n" block into its own notebook cell.
# =====================================================================

# CELL 1 — dependencies
# IMPORTANT: pin exact versions. An unpinned `%pip install xhtml2pdf`
# pulls the latest xhtml2pdf -> latest pyHanko -> a newer `cryptography`
# that conflicts with the Fabric environment's own msal/pyopenssl
# (which require cryptography <49 and <47 respectively). These pinned
# versions match the working combination from the original
# notebooks/requirements.txt and satisfy both constraints at once.
# %pip install xhtml2pdf==0.2.17 cryptography==46.0.7 reportlab==4.4.10 --quiet
# After this cell finishes, RESTART THE KERNEL (Fabric notebook toolbar:
# "Restart session" or similar) before running any further cell — the
# wrong cryptography version may already be loaded in memory from
# msal/pyopenssl imports that happened when the session started.

import pandas as pd
import smtplib
from email.message import EmailMessage
from xhtml2pdf import pisa
from io import BytesIO
import os
import notebookutils

WAREHOUSE_NAME = "GestaoDespesasDW"
OUTPUT_FOLDER = "/lakehouse/default/Files/Output_Obras"

# CELL 2 — parameters cell
# Toggle as "parameter cell" in the Fabric UI (same pattern as the other
# notebooks). Fill in manually for now; the Pipeline (Step 5) will inject
# these later. SMTP_SERVER/PORT are not secret, so they stay as plain
# constants below rather than parameters.
EMAIL_REMETENTE = "<PASTE_SENDER_EMAIL_HERE>"
EMAIL_PASSWORD = "<PASTE_SENDER_APP_PASSWORD_HERE>"
EMAIL_DESTINO = "<PASTE_DESTINATION_EMAIL_HERE>"

SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587

# CELL 3 — connection helper (same pattern as the other notebooks)
def get_warehouse_connection():
    return notebookutils.data.connect_to_artifact(WAREHOUSE_NAME)

# CELL 4 — quick connectivity test
conn = get_warehouse_connection()
result = conn.query("SELECT ISNULL(SUM([Valor Gasto (€)]), 0) AS TotalAcumulado FROM dbo.vw_Fact_Obras")
print("Total acumulado em Obras:", result["TotalAcumulado"][0])

# CELL 5 — fetch data (total + detail), but ONLY if there's something new
# to report. Mirrors the Telegram outbox pattern (architecture.md §5):
# state lives in the database (Notificado_Email), not in run-to-run logic.
conn = get_warehouse_connection()

pendentes_result = conn.query("SELECT COUNT(*) AS cnt FROM dw.Fact_Obras WHERE Notificado_Email = 0")
pendentes_count = pendentes_result["cnt"][0]
print(f"Linhas de Obras pendentes de notificação por email: {pendentes_count}")

if pendentes_count == 0:
    print("Nada de novo desde o último envio — a saltar geração/envio do relatório.")
else:
    total_result = conn.query("SELECT ISNULL(SUM([Valor Gasto (€)]), 0) AS TotalAcumulado FROM dbo.vw_Fact_Obras")
    total_obras = float(total_result["TotalAcumulado"][0])

    detalhe_query = """
        SELECT CAST(Data AS DATE) as Data, [Descrição] as Descricao, [Valor Gasto (€)] as Valor
        FROM dbo.vw_Fact_Obras ORDER BY Data DESC
    """
    df_obras = conn.query(detalhe_query)
    if df_obras is None:
        df_obras = pd.DataFrame(columns=["Data", "Descricao", "Valor"])

    print(f"Total acumulado: {total_obras:,.2f} €")
    print(f"Linhas de detalhe (histórico completo, não só as pendentes): {len(df_obras)}")

# CELL 6 — generate the PDF (same layout/logic as the legacy script)
# Only runs if there was something pending (Cell 5 set pendentes_count).
def gerar_pdf(df_obras, total_acumulado):
    df_pdf = df_obras.copy()
    if not df_pdf.empty:
        df_pdf["Data"] = pd.to_datetime(df_pdf["Data"]).dt.strftime("%d/%m/%Y")
        df_pdf["Valor"] = df_pdf["Valor"].apply(lambda x: f"{x:,.2f} €")

    html = f"""
    <html><head><style>
        @page {{ size: A4; margin: 1cm; }}
        body {{ font-family: Helvetica, sans-serif; font-size: 10pt; }}
        h2 {{ color: #0078D4; border-bottom: 2px solid #0078D4; padding-bottom: 5px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background-color: #f2f2f2; padding: 8px; border: 1px solid #ddd; text-align: left; }}
        td {{ padding: 8px; border: 1px solid #ddd; }}
    </style></head>
    <body>
        <h2>Histórico de Gastos em Obras - {pd.Timestamp.now().strftime("%d/%m/%Y")}</h2>
        <p style="font-size: 1.2em;">Total acumulado: <b>{total_acumulado:,.2f} €</b></p>
        {df_pdf.to_html(index=False, border=0, justify="left") if not df_pdf.empty else "<p>Sem registos de Obras.</p>"}
    </body></html>
    """
    buffer = BytesIO()
    pisa.CreatePDF(html, dest=buffer)
    buffer.seek(0)
    return buffer.read()

if pendentes_count > 0:
    pdf_bytes = gerar_pdf(df_obras, total_obras)
    print(f"PDF gerado: {len(pdf_bytes)} bytes")

# CELL 7 — save the PDF into this Lakehouse's Files area
if pendentes_count > 0:
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    hoje_fmt = pd.Timestamp.now().strftime("%Y%m%d")
    nome_pdf = f"Relatorio_Obras_{hoje_fmt}.pdf"
    caminho_pdf = os.path.join(OUTPUT_FOLDER, nome_pdf)

    with open(caminho_pdf, "wb") as f:
        f.write(pdf_bytes)

    print(f"PDF guardado em: {caminho_pdf}")

# CELL 8 — send the email with the PDF attached
def enviar_email(total_acumulado, pdf_bytes, nome_pdf):
    html = f"""
    <html><body style="font-family: Segoe UI, Arial, sans-serif; color: #333;">
        <h2 style="color: #0078D4;">🏗️ Atualização de Obras</h2>
        <p style="font-size: 1.2em;">Total gasto em obras até agora: <b>{total_acumulado:,.2f} €</b></p>
        <p>Segue em anexo o relatório detalhado em PDF.</p>
        <hr style="border: 0; border-top: 1px solid #eee;">
        <p style="font-size: 0.8em; color: #888;">Gerado automaticamente pelo Sistema de Gestão Financeira (Fabric).</p>
    </body></html>
    """
    msg = EmailMessage()
    msg["Subject"] = f"Relatório de Obras - Acumulado: {total_acumulado:,.2f} €"
    msg["From"], msg["To"] = EMAIL_REMETENTE, EMAIL_DESTINO
    msg.add_alternative(html, subtype="html")
    msg.add_attachment(pdf_bytes, maintype="application", subtype="pdf", filename=nome_pdf)

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, local_hostname=EMAIL_REMETENTE.split("@")[-1]) as server:
        server.starttls()
        server.login(EMAIL_REMETENTE, EMAIL_PASSWORD)
        server.send_message(msg)

if pendentes_count > 0:
    enviar_email(total_obras, pdf_bytes, nome_pdf)
    print("Email enviado com sucesso.")

# CELL 9 — mark all currently-pending Obras rows as notified (outbox
# pattern close-out). Only runs when something was actually sent.
if pendentes_count > 0:
    conn = get_warehouse_connection()
    conn.query("UPDATE dw.Fact_Obras SET Notificado_Email = 1 WHERE Notificado_Email = 0")
    print(f"{pendentes_count} linha(s) de Obras marcada(s) como notificadas por email.")
