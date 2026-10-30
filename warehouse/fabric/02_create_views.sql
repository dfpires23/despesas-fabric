-- GestaoDespesasDW — reporting views consumed by Power BI.
-- Output aliases keep the original names; base-table columns are accent/space-free.
 
CREATE OR ALTER VIEW [dbo].[vw_Dim_Categoria] AS
SELECT 
    C.ID_Categoria AS [Categoria Key],
    C.Categoria,
    C.Subcategoria,
    C.Natureza,
    C.Prioridade,
    C.Fonte,
    C.Icone_SVG AS [Ícone SVG]
FROM dw.Dim_Categoria AS C;
GO
 
CREATE OR ALTER VIEW [dbo].[vw_Fact_Budget] AS
SELECT 
    B.ID_Categoria AS [Categoria Key],
    B.Data_Referencia AS [Data],
    B.Valor AS [Valor Orçamentado (€)]
FROM dw.Fact_Budget AS B;
GO
 
CREATE OR ALTER VIEW [dbo].[vw_Fact_DespesasReais] AS
SELECT 
    D.ID_Categoria AS [Categoria Key],
    D.Data_Despesa AS [Data],
    D.Valor AS [Valor Gasto (€)],
    D.Descricao AS [Descrição]
FROM dw.Fact_DespesasReais AS D;
GO
 
CREATE OR ALTER VIEW [dbo].[vw_Fact_Receitas] AS
SELECT 
    R.ID_Categoria AS [Categoria Key],
    R.Data_Receita AS [Data],
    R.Valor AS [Valor Recebido (€)],
    R.Descricao AS [Descrição]
FROM dw.Fact_Receitas AS R;
GO
 
CREATE OR ALTER VIEW [dbo].[vw_Dim_Calendario] AS
SELECT
    C.Data,
    C.Ano,
    C.MesNo        AS [Mês Nº],
    C.MesCurto     AS [Mês (Curto)],
    C.MesRelativo  AS [Mês Relativo],
    C.MesAtual     AS [Mês Atual],
    C.DiaAtual     AS [Dia Atual]
FROM dbo.Dim_Calendario AS C;
GO
 
CREATE OR ALTER VIEW [dbo].[vw_Meta_Controlo] AS
SELECT Modulo, Ultima_Atualizacao AS [Última Atualização] FROM dw.Meta_Controlo;
GO
 
CREATE OR ALTER VIEW [dbo].[vw_Dim_MetasMensais] AS
SELECT
    DATEFROMPARTS(M.Ano, M.Mes, 1) AS [Data],
    M.Pct_Poupanca AS [Pct Poupança],
    M.Pct_Extras AS [Pct Extras]
FROM dw.Dim_MetasMensais AS M;
GO
 
CREATE OR ALTER VIEW [dbo].[vw_Fact_Obras] AS
SELECT 
    O.ID_Categoria AS [Categoria Key],
    O.Data_Despesa AS [Data],
    O.Valor AS [Valor Gasto (€)],
    O.Descricao AS [Descrição]
FROM dw.Fact_Obras AS O;
GO
 
CREATE OR ALTER VIEW [dbo].[vw_Fact_Saldos] AS
SELECT 
    S.ID_Categoria AS [Categoria Key],
    S.Data_Saldo AS [Data],
    S.Valor AS [Valor Real (€)],
    S.Descricao AS [Descrição]
FROM dw.Fact_Saldos AS S;
GO
 