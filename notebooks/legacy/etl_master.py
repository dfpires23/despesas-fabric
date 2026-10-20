import pandas as pd
import gspread
import requests
import urllib
import os
import msal
import sys
import traceback
import time
from datetime import datetime
from oauth2client.service_account import ServiceAccountCredentials
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from obras_report import executar_fluxo_report_obras

load_dotenv()

# --- CONFIGURAÇÕES GERAIS ---
PASTA_BUDGET = r"G:\My Drive\FamilyDocs\O Nosso Orçamento\Input_Budgets"
JSON_KEYFILE = "credentials.json"
SHEET_DESPESAS = "Despesas_Reais_DB"

# SQL Server
SERVER = os.getenv("SQL_SERVER")
DATABASE = os.getenv("SQL_DATABASE")
DRIVER = "ODBC Driver 17 for SQL Server"

# Power BI API
CLIENT_ID = os.getenv("PBI_CLIENT_ID")
CLIENT_SECRET = os.getenv("PBI_CLIENT_SECRET")
TENANT_ID = os.getenv("PBI_TENANT_ID")
GROUP_ID = "6c5985be-1cf0-4466-b1da-28c17ed94318"
DATASET_ID = "9e7c1dce-89c6-4553-a364-8acb4dec732c"

# --- Criar engine SQLAlchemy ---
try:
    params = urllib.parse.quote_plus(
        f"DRIVER={DRIVER};SERVER={SERVER};DATABASE={DATABASE};Trusted_Connection=yes;TrustServerCertificate=yes;"
    )
    engine = create_engine(
        f"mssql+pyodbc:///?odbc_connect={params}",
        fast_executemany=True,
        pool_pre_ping=True,
        pool_recycle=3600,
    )
except Exception as e:
    print(f"[FATAL] Erro ao criar engine SQL: {e}")
    sys.exit(1)


def log(mensagem, nivel="INFO"):
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"

    cores = {"INFO": CYAN, "SUCCESS": GREEN, "WARN": YELLOW, "ERROR": RED, "FATAL": RED}

    cor = cores.get(nivel, RESET)
    tag = f"{cor}[{nivel}]{RESET}"
    print(f"{tag} {mensagem}")
    sys.stdout.flush()


# --- Função para enviar resumo das novas despesas para Telegram ---
def enviar_resumo_telegram(df_novos):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if df_novos.empty:
        return

    for i in range(0, len(df_novos), 20):
        chunk = df_novos.iloc[i : i + 20]
        mensagem = f"✅ <b>Processamento ({i + 1} a {i + len(chunk)} de {len(df_novos)}):</b>\n\n"

        for _, row in chunk.iterrows():
            valor_formatado = f"{float(row['Valor']):,.2f} €"
            mensagem += f"{row['Data_Despesa']}, {row['Categoria_Full']}\n"
            mensagem += f"{valor_formatado}, {row['Descricao']}\n"
            mensagem += "\n"

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": mensagem, "parse_mode": "HTML"}

        try:
            requests.post(url, data=payload, timeout=10)
            time.sleep(1)
        except Exception as e:
            print(f"Erro ao enviar Telegram: {e}")


# --- Função para obter carimbos já existentes nas fact tables ---
def obter_carimbos_existentes():
    query = """
    SELECT Carimbo_Original FROM dw.Fact_DespesasReais WHERE Carimbo_Original IS NOT NULL
    UNION
    SELECT Carimbo_Original FROM dw.Fact_Obras WHERE Carimbo_Original IS NOT NULL
    UNION
    SELECT Carimbo_Original FROM dw.Fact_Receitas WHERE Carimbo_Original IS NOT NULL
    UNION
    SELECT Carimbo_Original FROM dw.Fact_Saldos WHERE Carimbo_Original IS NOT NULL
    """
    with engine.connect() as conn:
        df_existentes = pd.read_sql(text(query), conn)
        return df_existentes["Carimbo_Original"].astype(str).tolist()


# --- 1. ETL BUDGET (Excel -> SQL) ---
def processar_budget():
    log("Iniciando processamento do Budget...")

    if not os.path.exists(PASTA_BUDGET):
        raise FileNotFoundError(f"Diretoria não encontrada: {PASTA_BUDGET}")

    arquivos = [
        f
        for f in os.listdir(PASTA_BUDGET)
        if "Budget_" in f and f.endswith(".xlsx") and not f.startswith("~$")
    ]

    if not arquivos:
        log("Nenhum ficheiro de Budget encontrado.", "WARN")
        return

    # Limpar tabela antes de carregar
    try:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE stg.Budget"))
    except Exception as e:
        log(f"Erro ao truncar tabela Budget: {e}", "ERROR")
        raise e

    # Loop para carregar ficheiros
    for ficheiro in arquivos:
        log(f"Processando ficheiro: {ficheiro}")
        try:
            ano = int(ficheiro.replace("Budget_", "").replace(".xlsx", ""))
            df = pd.read_excel(os.path.join(PASTA_BUDGET, ficheiro), engine="openpyxl")

            colunas_fixas = [
                "Categoria",
                "Subcategoria",
                "Tipo",
                "Natureza",
                "Fonte de Pagamento",
            ]
            cols_meses = [c for c in df.columns if c not in colunas_fixas]

            df_unpivoted = df.melt(
                id_vars=colunas_fixas,
                value_vars=cols_meses,
                var_name="Mes",
                value_name="Valor",
            )

            df_unpivoted = df_unpivoted.rename(
                columns={"Fonte de Pagamento": "Fonte", "Tipo": "Prioridade"}
            )

            df_unpivoted["Ano"] = ano
            df_unpivoted["Valor"] = df_unpivoted["Valor"].fillna(0)

            df_unpivoted.to_sql(
                "Budget",
                schema="stg",
                con=engine,
                index=False,
                if_exists="append",
                chunksize=1000,
            )

        except Exception as e:
            log(f"Falha ao processar ficheiro {ficheiro}: {e}", "ERROR")
            raise e

    # Processar Procedure Final
    try:
        with engine.begin() as conn:
            conn.execute(text("EXEC sp_ProcessarBudget"))
            log("SP sp_ProcessarBudget executada com sucesso.", "SUCCESS")
    except Exception as e:
        log(f"Falha na execução da SP de Budget: {e}", "ERROR")
        raise e


# --- 2. ETL METAS DINÂMICAS ---
def processar_metas_dinamicas():
    log("Iniciando processamento de Metas Mensais...")

    arquivos = [
        f
        for f in os.listdir(PASTA_BUDGET)
        if "Budget_" in f and f.endswith(".xlsx") and not f.startswith("~$")
    ]
    df_final = pd.DataFrame()

    for ficheiro in arquivos:
        try:
            ano = int(ficheiro.replace("Budget_", "").replace(".xlsx", ""))
            caminho = os.path.join(PASTA_BUDGET, ficheiro)

            try:
                df = pd.read_excel(caminho, sheet_name="Sheet4", engine="openpyxl")
            except ValueError:
                continue

            df = df.rename(
                columns={
                    "Mês": "Mes",
                    "Poupança": "Pct_Poupanca",
                    "Extras": "Pct_Extras",
                }
            )

            # Validação simples
            required_cols = ["Mes", "Pct_Poupanca", "Pct_Extras"]
            if all(col in df.columns for col in required_cols):
                df["Ano"] = ano
                df_final = pd.concat([df_final, df])

        except Exception as e:
            log(f"Erro ao ler metas de {ficheiro}: {e}", "WARN")

    if not df_final.empty:
        df_final["Mes"] = pd.to_numeric(df_final["Mes"], errors="coerce")
        df_final["Pct_Poupanca"] = pd.to_numeric(
            df_final["Pct_Poupanca"], errors="coerce"
        ).fillna(0)
        df_final["Pct_Extras"] = pd.to_numeric(
            df_final["Pct_Extras"], errors="coerce"
        ).fillna(0)

        try:
            with engine.begin() as conn:
                conn.execute(text("TRUNCATE TABLE dw.Dim_MetasMensais"))
                df_final.to_sql(
                    "Dim_MetasMensais",
                    schema="dw",
                    con=conn,
                    index=False,
                    if_exists="append",
                    chunksize=1000,
                )
                log(f"{len(df_final)} registos de metas carregados.", "SUCCESS")
        except Exception as e:
            log(f"Erro SQL ao gravar Metas: {e}", "ERROR")
            raise e


# --- 3. ETL DESPESAS REAIS (Google Sheets) ---
def processar_despesas_reais():
    log("Iniciando extração do Google Sheets...")
    count_obras = 0

    try:
        # Extração GSheets (com logs de progresso)
        creds = ServiceAccountCredentials.from_json_keyfile_name(
            JSON_KEYFILE,
            [
                "https://spreadsheets.google.com/feeds",
                "https://www.googleapis.com/auth/drive",
            ],
        )
        client = gspread.authorize(creds)
        log(f"Conectado ao Drive. Abrindo {SHEET_DESPESAS}...")
        sheet = client.open(SHEET_DESPESAS).sheet1
        df = pd.DataFrame(sheet.get_all_records())
        log("Extração do Google Sheets concluída.", "SUCCESS")
    except Exception as e:
        log(f"Erro no Google Sheets: {e}", "ERROR")
        return False

    if df.empty:
        return False

    # Tratamento de dados
    df = df.rename(
        columns={
            df.columns[0]: "Carimbo",
            df.columns[1]: "Data_Despesa",
            df.columns[2]: "Valor",
            df.columns[3]: "Categoria_Full",
            df.columns[4]: "Descricao",
        }
    )
    df["Carimbo"] = df["Carimbo"].astype(str)
    df_novos = df[~df["Carimbo"].isin(obter_carimbos_existentes())].copy()
    df_novos["Data_Despesa"] = pd.to_datetime(df_novos["Data_Despesa"], errors="coerce")
    df_novos["Data_Despesa"] = df_novos["Data_Despesa"].dt.strftime("%Y-%m-%d")
    df_novos["Valor"] = df_novos["Valor"].replace(r'[€$\s,]', '', regex=True)

    if df_novos.empty:
        log("Tudo atualizado. Nenhuma linha nova encontrada.")
        return False

    # Telegram em Chunks
    enviar_resumo_telegram(df_novos)
    log(f"Enviadas {len(df_novos)} notificações para o Telegram.", "SUCCESS")

    try:
        # SQL Transacional
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE stg.DespesasReais"))
            df_novos.to_sql(
                "DespesasReais", schema="stg", con=conn, index=False, if_exists="append"
            )

            # Verificação de Obras
            q = text(
                "SELECT COUNT(*) FROM stg.DespesasReais WHERE Categoria_Full LIKE 'Obras%'"
            )
            count_obras = conn.execute(q).scalar()

            conn.execute(text("EXEC sp_ProcessarDespesasReais"))
            log(
                f"SQL: {len(df_novos)} linhas movidas para o Data Warehouse.", "SUCCESS"
            )

        if count_obras > 0:
            log(
                f"Detetadas {count_obras} novas entradas de Obras. Gerando relatório..."
            )
            if executar_fluxo_report_obras(engine):
                log(
                    "Relatório de Obras enviado por Email e guardado no Drive!",
                    "SUCCESS",
                )

        return True
    except Exception as e:
        log(f"Erro no processamento SQL: {e}", "ERROR")
        raise e


# --- Obter ano mínimo e máximo para atualização de feriados e calendário ---
def obter_intervalo_anos():
    log("Obtendo intervalo de anos...")
    try:
        with engine.connect() as conn:
            query_anos = """
                SELECT MIN(Ano), MAX(Ano) FROM (
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
            min_year, max_year = conn.execute(text(query_anos)).fetchone()

        if not min_year:
            min_year = max_year = datetime.now().year
        log(f"Ano mínimo: {min_year}, Ano máximo: {max_year}")
        return min_year, max_year
    except Exception as e:
        log(f"Erro ao obter intervalo de anos: {e}", "ERROR")
        raise e


# --- 4. ATUALIZAR FERIADOS ---
def atualizar_feriados(min_year, max_year):
    log("Verificando atualização de feriados...")
    try:
        todos_feriados = []

        for ano in range(min_year, max_year + 1):
            url = f"https://date.nager.at/api/v3/PublicHolidays/{ano}/PT"
            try:
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    df_fer = pd.DataFrame(resp.json())
                    if not df_fer.empty:
                        df_temp = pd.DataFrame(
                            {"Data": df_fer["date"], "FeriadoNome": df_fer["localName"]}
                        )
                        todos_feriados.append(df_temp)
                        log(f"Feriados {ano}: OK")
                else:
                    log(f"API retornou status {resp.status_code} para {ano}", "WARN")
            except Exception as e:
                log(f"Erro ao baixar feriados {ano} (timeout/rede): {e}", "WARN")

        if todos_feriados:
            df_final = pd.concat(todos_feriados)

            with engine.begin() as conn:
                conn.execute(text("TRUNCATE TABLE FeriadosPT"))
                df_final.to_sql(
                    "FeriadosPT",
                    schema="dbo",
                    con=conn,
                    index=False,
                    if_exists="append",
                    chunksize=1000,
                )
                log(f"{len(df_final)} feriados carregados com sucesso.", "SUCCESS")
    except Exception as e:
        log(f"Erro no processo de feriados: {e}", "ERROR")
        raise e


# --- 5. TAREFAS DE MANUTENÇÃO SQL ---
def recarregar_calendario(min_year, max_year):
    log("Executando sp_AtualizarCalendario...")
    try:
        with engine.begin() as conn:
            conn.execute(
                text("EXEC sp_AtualizarCalendario @AnoInicio=:inicio, @AnoFim=:fim"),
                {"inicio": min_year, "fim": max_year},
            )
            log("Calendário atualizado com sucesso.", "SUCCESS")
    except Exception as e:
        log(f"Erro ao atualizar calendário: {e}", "ERROR")
        raise e


def atualizar_meta_controlo():
    log("Registando timestamp de execução...")
    try:
        with engine.begin() as conn:
            conn.execute(text("TRUNCATE TABLE dw.Meta_Controlo"))
            conn.execute(
                text(
                    "INSERT INTO dw.Meta_Controlo (Modulo, Ultima_Atualizacao) VALUES ('Geral', GETDATE())"
                )
            )
            log("Timestamp de execução registado com sucesso.", "SUCCESS")
    except Exception as e:
        log(f"Erro ao registar log: {e}", "ERROR")
        raise e


# --- 6. POWER BI REFRESH ---
def trigger_pbi_refresh():
    log("Solicitando refresh do Power BI Dataset...")

    authority_url = f"https://login.microsoftonline.com/{TENANT_ID}"
    scopes = ["https://analysis.windows.net/powerbi/api/.default"]

    try:
        app = msal.ConfidentialClientApplication(
            CLIENT_ID, authority=authority_url, client_credential=CLIENT_SECRET
        )
        result = app.acquire_token_for_client(scopes=scopes)

        if "access_token" not in result:
            raise Exception(f"Falha na autenticação Azure AD: {result.get('error')}")

        headers = {"Authorization": f"Bearer {result['access_token']}"}
        refresh_url = f"https://api.powerbi.com/v1.0/myorg/groups/{GROUP_ID}/datasets/{DATASET_ID}/refreshes"

        response = requests.post(refresh_url, headers=headers, timeout=10)

        if response.status_code in [200, 202]:
            log("Refresh PBI solicitado com sucesso.", "SUCCESS")
        else:
            raise Exception(
                f"API retornou erro {response.status_code}: {response.text}"
            )

        max_retries = 30

        for i in range(max_retries):
            log("Verificando status do refresh do Power BI Dataset...")
            time.sleep(30)  # Espera 30 segundos

            try:
                # Pede o histórico dos últimos refreshes (top=1)
                status_resp = requests.get(f"{refresh_url}?$top=1", headers=headers)
            except requests.exceptions.RequestException as e:
                log(f"Erro ao verificar status do refresh (timeout/rede): {e}", "WARN")
                continue

            if status_resp.status_code == 200:
                data = status_resp.json()
                if "value" in data and len(data["value"]) > 0:
                    latest_refresh = data["value"][0]
                    status = latest_refresh.get("status")

                    if status == "Completed":
                        log("Refresh PBI concluído com sucesso!", "SUCCESS")
                        return

                    elif status == "Failed":
                        error_detail = latest_refresh.get(
                            "serviceExceptionJson", "Sem detalhes"
                        )
                        raise Exception(
                            f"O Power BI falhou o refresh! Status: {status}. Detalhe: {error_detail}"
                        )

                    else:
                        # Status pode ser 'Unknown' ou 'Executing'
                        log(f"Ainda a processar... (Tentativa {i + 1}/{max_retries})")
                else:
                    log("Não foi possível ler o estado do refresh.", "WARN")
            else:
                log(f"Erro ao verificar estado: {status_resp.status_code}", "WARN")

        # Se sair do loop sem return, é porque excedeu o tempo
        raise TimeoutError(
            "O Refresh demorou mais de 15 minutos e o script desistiu de esperar."
        )

    except Exception as e:
        log(f"Erro no processo PBI: {e}", "ERROR")
        raise e


# --- MAIN EXECUTION ---
if __name__ == "__main__":
    try:
        print("=" * 50)
        log("INICIANDO PROCESSO ETL")
        print("=" * 50)

        processar_budget()
        processar_metas_dinamicas()

        # Retorna True se houve novas despesas processadas, False caso contrário
        houve_novas_despesas = processar_despesas_reais()

        if houve_novas_despesas:
            min_year, max_year = obter_intervalo_anos()
            atualizar_feriados(min_year, max_year)
            recarregar_calendario(min_year, max_year)
            atualizar_meta_controlo()
            trigger_pbi_refresh()
        else:
            log("Ignorando manutenção e refresh do Power BI.")

        print("=" * 50)
        log("PROCESSO CONCLUÍDO COM SUCESSO")
        print("=" * 50)
        sys.exit(0)

    except Exception as e:
        print("\n" + "!" * 50)
        log("ERRO CRÍTICO DETETADO - ETL ABORTADO", "FATAL")
        print("!" * 50)
        traceback.print_exc()
        sys.exit(1)
