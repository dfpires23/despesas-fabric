-- =====================================================================
-- GestaoDespesasDW — Fabric Warehouse Views (Step 2, continued)
-- Adapted from refresh_views.sql (SQL Server baseline)
--
-- Adaptations:
--   * Removed "USE [GestaoDespesas]" — not needed; the SQL editor is
--     already bound to this Warehouse.
--   * CREATE OR ALTER VIEW is confirmed supported in Fabric Warehouse —
--     kept as-is.
--   * dbo.Dim_Calendario column references updated to match the renamed
--     (space/accent-free) columns created in Step 2:
--       [Mês Nº]        -> MesNo
--       [Mês (Curto)]   -> MesCurto
--       [Mês Relativo]  -> MesRelativo
--       [Mês Atual]     -> MesAtual
--       [Dia Atual]     -> DiaAtual
--     The output column aliases (what Power BI actually sees, e.g.
--     [Mês Nº] as an alias) are kept identical to the original, so this
--     is invisible to the semantic model.
-- =====================================================================

-- === 1. VIEW DIMENSÃO CATEGORIA ===
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

-- === 2. VIEW FACTO BUDGET ===
CREATE OR ALTER VIEW [dbo].[vw_Fact_Budget] AS
SELECT 
    B.ID_Categoria AS [Categoria Key],
    B.Data_Referencia AS [Data],
    B.Valor AS [Valor Orçamentado (€)]
FROM dw.Fact_Budget AS B;
GO

-- === 3. VIEW FACTO DESPESAS REAIS ===
CREATE OR ALTER VIEW [dbo].[vw_Fact_DespesasReais] AS
SELECT 
    D.ID_Categoria AS [Categoria Key],
    D.Data_Despesa AS [Data],
    D.Valor AS [Valor Gasto (€)],
    D.Descricao AS [Descrição]
FROM dw.Fact_DespesasReais AS D;
GO

-- === 4. VIEW FACTO RECEITAS ===
CREATE OR ALTER VIEW [dbo].[vw_Fact_Receitas] AS
SELECT 
    R.ID_Categoria AS [Categoria Key],
    R.Data_Receita AS [Data],
    R.Valor AS [Valor Recebido (€)],
    R.Descricao AS [Descrição]
FROM dw.Fact_Receitas AS R;
GO

-- === 5. VIEW CALENDÁRIO ===
CREATE OR ALTER VIEW [dbo].[vw_Dim_Calendario] AS
SELECT
    C.Data,
    C.Ano,
    C.MesNo        AS [Mês Nº],
    C.MesCurto      AS [Mês (Curto)],
    C.MesRelativo  AS [Mês Relativo],
    C.MesAtual     AS [Mês Atual],
    C.DiaAtual     AS [Dia Atual]
FROM dbo.Dim_Calendario AS C;
GO

-- === 6. VIEW CONTROLO ===
CREATE OR ALTER VIEW [dbo].[vw_Meta_Controlo] AS
SELECT Modulo, Ultima_Atualizacao AS [Última Atualização] FROM dw.Meta_Controlo;
GO

-- === 7. VIEW METAS MENSAIS ===
CREATE OR ALTER VIEW [dbo].[vw_Dim_MetasMensais] AS
SELECT
    DATEFROMPARTS(M.Ano, M.Mes, 1) AS [Data],
    M.Pct_Poupanca AS [Pct Poupança],
    M.Pct_Extras AS [Pct Extras]
FROM dw.Dim_MetasMensais AS M;
GO

-- === 8. VIEW OBRAS ===
CREATE OR ALTER VIEW [dbo].[vw_Fact_Obras] AS
SELECT 
    O.ID_Categoria AS [Categoria Key],
    O.Data_Despesa AS [Data],
    O.Valor AS [Valor Gasto (€)],
    O.Descricao AS [Descrição]
FROM dw.Fact_Obras AS O;
GO

-- === 9. VIEW SALDOS ===
CREATE OR ALTER VIEW [dbo].[vw_Fact_Saldos] AS
SELECT 
    S.ID_Categoria AS [Categoria Key],
    S.Data_Saldo AS [Data],
    S.Valor AS [Valor Real (€)],
    S.Descricao AS [Descrição]
FROM dw.Fact_Saldos AS S;
GO
