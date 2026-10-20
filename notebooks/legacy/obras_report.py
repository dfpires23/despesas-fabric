import os
import pandas as pd
import smtplib
from email.message import EmailMessage
from sqlalchemy import text
from xhtml2pdf import pisa
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURAÇÕES ---
FOLDER_OUTPUT = r"G:\My Drive\FamilyDocs\O Nosso Orçamento\Output_Obras"
SMTP_SERVER = "smtp.office365.com"
SMTP_PORT = 587
EMAIL_REMETENTE = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASS")
EMAIL_DESTINO = os.getenv("EMAIL_DESTINO")


def get_data(engine):
    # Agora a query foca-se apenas no total acumulado das obras
    sql_kpi_obras = "SELECT ISNULL(SUM([Valor Gasto (€)]), 0) as TotalAcumulado FROM dbo.vw_Fact_Obras"

    sql_obras_detalhe = """
    SELECT CAST(Data AS DATE) as Data, [Descrição] as Descricao, [Valor Gasto (€)] as Valor 
    FROM dbo.vw_Fact_Obras ORDER BY Data DESC
    """

    with engine.connect() as conn:
        total_obras = conn.execute(text(sql_kpi_obras)).scalar()
        df_obras = pd.read_sql(text(sql_obras_detalhe), conn).fillna(0)

    return total_obras, df_obras


def gerar_excel(df_obras, hoje_fmt):
    if not os.path.exists(FOLDER_OUTPUT):
        os.makedirs(FOLDER_OUTPUT, exist_ok=True)

    file_path = os.path.join(FOLDER_OUTPUT, f"Relatorio_Obras_{hoje_fmt}.xlsx")
    with pd.ExcelWriter(file_path, engine="xlsxwriter") as writer:
        df_obras.to_excel(writer, sheet_name="Obras", index=False)
        workbook, worksheet = writer.book, writer.sheets["Obras"]
        money_fmt = workbook.add_format({"num_format": "#,##0.00 €"})
        date_fmt = workbook.add_format({"num_format": "dd/mm/yyyy"})
        worksheet.set_column("A:A", 12, date_fmt)
        worksheet.set_column("B:B", 40)
        worksheet.set_column("C:C", 15, money_fmt)
    return file_path


def gerar_pdf(df_obras):
    df_pdf = df_obras.copy()
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
        {df_pdf.to_html(index=False, border=0, justify="left")}
    </body></html>
    """
    buffer = BytesIO()
    pisa.CreatePDF(html, dest=buffer)
    buffer.seek(0)
    return buffer.read()


def enviar_email(total_acumulado, pdf_bytes, nome_pdf):
    # Texto curto e direto como pediste
    html = f"""
    <html><body style="font-family: Segoe UI, Arial, sans-serif; color: #333;">
        <h2 style="color: #0078D4;">🏗️ Atualização de Obras</h2>
        <p style="font-size: 1.2em;">Total gasto em obras até agora: <b>{total_acumulado:,.2f} €</b></p>
        <p>Segue em anexo o relatório detalhado (PDF para leitura e Excel para arquivo).</p>
        <hr style="border: 0; border-top: 1px solid #eee;">
        <p style="font-size: 0.8em; color: #888;">Gerado automaticamente pelo Sistema de Gestão Financeira.</p>
    </body></html>
    """
    msg = EmailMessage()
    msg["Subject"] = f"Relatório de Obras - Acumulado: {total_acumulado:,.2f} €"
    msg["From"], msg["To"] = EMAIL_REMETENTE, EMAIL_DESTINO
    msg.add_alternative(html, subtype="html")
    msg.add_attachment(
        pdf_bytes, maintype="application", subtype="pdf", filename=nome_pdf
    )

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
        server.starttls()
        server.login(EMAIL_REMETENTE, EMAIL_PASSWORD)
        server.send_message(msg)


def executar_fluxo_report_obras(engine):
    hoje_fmt = pd.Timestamp.now().strftime("%Y%m%d")

    # 1. Obter total acumulado e a tabela de detalhes
    total_acumulado, df_obras = get_data(engine)

    if not df_obras.empty:
        # 2. Gerar o Excel no Drive
        gerar_excel(df_obras, hoje_fmt)

        # 3. Gerar PDF e enviar e-mail
        pdf_bytes = gerar_pdf(df_obras)
        enviar_email(total_acumulado, pdf_bytes, f"Relatorio_Obras_{hoje_fmt}.pdf")
        return True
    return False
