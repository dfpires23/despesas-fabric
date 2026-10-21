-- =====================================================================
-- GestaoDespesasDW — Fabric Warehouse DDL (Step 2)
-- Adapted from the SQL Server baseline (see docs/architecture.md)
--
-- Key adaptations for Fabric Warehouse T-SQL surface area:
--   * NVARCHAR -> VARCHAR (Fabric Warehouse has no NVARCHAR; UTF-8
--     collation already supports Portuguese accented characters)
--   * NVARCHAR(MAX) -> VARCHAR(MAX)
--   * IDENTITY columns must be BIGINT in Fabric Warehouse (INT IDENTITY
--     is rejected) — surrogate keys and their FK references are BIGINT
--   * IDENTITY has no custom seed/increment
--   * PRIMARY KEY / FOREIGN KEY CANNOT be declared inline in CREATE TABLE —
--     added afterwards via ALTER TABLE ... ADD CONSTRAINT ... NOT ENFORCED
--   * DEFAULT constraints are NOT supported at all (inline or via ALTER) —
--     Notificado_Telegram must be set explicitly to 0 by the INSERT that
--     populates these tables (handled in the Step 3 stored procedures)
--   * DATETIME -> DATETIME2
--
-- IDEMPOTENT: this script can be re-run safely during development.
-- It drops and recreates every table it manages. Do NOT re-run this
-- as-is once real data has been loaded — it would wipe it.
--
-- NOT included here: stored procedures (Step 3) and reporting views
-- (dbo.vw_*) — pending confirmation of exact view definitions.
-- =====================================================================

-- ---------------------------------------------------------------------
-- BLOCK 0 — CLEANUP (safe to re-run; drops only if they exist)
-- ---------------------------------------------------------------------
DROP TABLE IF EXISTS dw.Fact_Saldos;
DROP TABLE IF EXISTS dw.Fact_Receitas;
DROP TABLE IF EXISTS dw.Fact_Obras;
DROP TABLE IF EXISTS dw.Fact_DespesasReais;
DROP TABLE IF EXISTS dw.Fact_Budget;
DROP TABLE IF EXISTS dw.Dim_MetasMensais;
DROP TABLE IF EXISTS dw.Dim_Categoria;
DROP TABLE IF EXISTS dw.Meta_Controlo;
DROP TABLE IF EXISTS stg.Budget;
DROP TABLE IF EXISTS stg.DespesasReais;
DROP TABLE IF EXISTS dbo.Dim_Calendario;
DROP TABLE IF EXISTS dbo.FeriadosPT;
GO

-- ---------------------------------------------------------------------
-- BLOCK 1 — SCHEMAS (guarded — CREATE SCHEMA can't use IF NOT EXISTS
-- directly and must be the only statement in its batch, so we check first)
-- ---------------------------------------------------------------------
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'dw')
    EXEC('CREATE SCHEMA dw');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'stg')
    EXEC('CREATE SCHEMA stg');
GO
-- 'dbo' already exists by default in every Fabric Warehouse.

-- ---------------------------------------------------------------------
-- BLOCK 2 — TABLES (no inline constraints, no DEFAULT)
-- ---------------------------------------------------------------------

-- dbo — calendar & holidays
CREATE TABLE dbo.Dim_Calendario (
    Data                DATE            NOT NULL,
    Ano                 INT             NULL,
    Semestre            INT             NULL,
    SemestreAno         VARCHAR(20)     NULL,
    SemestreAnoId       INT             NULL,
    Trimestre           INT             NULL,
    TrimestreAno        VARCHAR(20)     NULL,
    TrimestreAnoId      INT             NULL,
    MesNo               INT             NULL,
    MesLongo            VARCHAR(20)     NULL,
    MesCurto            VARCHAR(10)     NULL,
    MesAno              VARCHAR(20)     NULL,
    MesAnoId            INT             NULL,
    DiaDaSemana         VARCHAR(20)     NULL,
    DiaDaSemanaNo       INT             NULL,
    TipoDeDia           VARCHAR(20)     NULL,
    MesRelativo         INT             NULL,
    MesAtual            VARCHAR(10)     NULL,
    DiaAtual            VARCHAR(20)     NULL
);
GO

CREATE TABLE dbo.FeriadosPT (
    Data                DATE            NOT NULL,
    FeriadoNome         VARCHAR(100)    NULL
);
GO

-- dw — dimensional model
CREATE TABLE dw.Dim_Categoria (
    ID_Categoria        BIGINT IDENTITY NOT NULL,
    Categoria           VARCHAR(100)    NULL,
    Subcategoria        VARCHAR(100)    NULL,
    Natureza            VARCHAR(50)     NULL,
    Prioridade          VARCHAR(50)     NULL,
    Fonte               VARCHAR(50)     NULL,
    Icone_SVG           VARCHAR(MAX)    NULL
);
GO

CREATE TABLE dw.Dim_MetasMensais (
    Ano                 INT             NULL,
    Mes                 INT             NULL,
    Pct_Poupanca        DECIMAL(5,2)    NULL,
    Pct_Extras          DECIMAL(5,2)    NULL,
    DtCarga             DATETIME2(0)    NULL
);
GO

CREATE TABLE dw.Fact_Budget (
    ID_Budget           BIGINT IDENTITY NOT NULL,
    ID_Categoria        BIGINT          NOT NULL,
    Data_Referencia     DATE            NULL,
    Valor               DECIMAL(10,2)   NULL
);
GO

CREATE TABLE dw.Fact_DespesasReais (
    ID_Despesa          BIGINT IDENTITY NOT NULL,
    ID_Categoria        BIGINT          NOT NULL,
    Data_Despesa        DATE            NULL,
    Valor               DECIMAL(10,2)   NULL,
    Descricao           VARCHAR(255)    NULL,
    Carimbo_Original    VARCHAR(100)    NULL,
    Notificado_Telegram BIT             NOT NULL,   -- outbox pattern (architecture.md §5); INSERTs must set this to 0 explicitly — DEFAULT not supported
    Telegram_Message_Id INT             NULL
);
GO

CREATE TABLE dw.Fact_Obras (
    ID_Obra             BIGINT IDENTITY NOT NULL,
    ID_Categoria        BIGINT          NOT NULL,
    Data_Despesa        DATE            NULL,
    Valor               DECIMAL(10,2)   NULL,
    Descricao           VARCHAR(255)    NULL,
    Carimbo_Original    VARCHAR(100)    NULL,
    Notificado_Telegram BIT             NOT NULL,
    Telegram_Message_Id INT             NULL
);
GO

CREATE TABLE dw.Fact_Receitas (
    ID_Receita          BIGINT IDENTITY NOT NULL,
    ID_Categoria        BIGINT          NOT NULL,
    Data_Receita        DATE            NULL,
    Valor               DECIMAL(10,2)   NULL,
    Descricao           VARCHAR(255)    NULL,
    Carimbo_Original    VARCHAR(100)    NULL,
    Notificado_Telegram BIT             NOT NULL,
    Telegram_Message_Id INT             NULL
);
GO

CREATE TABLE dw.Fact_Saldos (
    ID_Saldo            BIGINT IDENTITY NOT NULL,
    ID_Categoria        BIGINT          NOT NULL,
    Data_Saldo          DATE            NULL,
    Valor               DECIMAL(10,2)   NULL,
    Descricao           VARCHAR(255)    NULL,
    Carimbo_Original    VARCHAR(100)    NULL,
    Notificado_Telegram BIT             NOT NULL,
    Telegram_Message_Id INT             NULL
);
GO

CREATE TABLE dw.Meta_Controlo (
    Modulo              VARCHAR(50)     NULL,
    Ultima_Atualizacao  DATETIME2(0)    NULL
);
GO

-- stg — staging (untyped where the source is inherently unreliable,
-- matching the current design's philosophy of casting only on load to dw)
CREATE TABLE stg.Budget (
    Categoria           VARCHAR(100)    NULL,
    Subcategoria        VARCHAR(100)    NULL,
    Prioridade          VARCHAR(50)     NULL,
    Natureza            VARCHAR(50)     NULL,
    Fonte               VARCHAR(50)     NULL,
    Mes                 VARCHAR(20)     NULL,
    Valor               DECIMAL(10,2)   NULL,
    Ano                 INT             NULL,
    DtCarga             DATETIME2(0)    NULL
);
GO

CREATE TABLE stg.DespesasReais (
    Carimbo             VARCHAR(100)    NULL,
    Data_Despesa        VARCHAR(50)     NULL,   -- kept as text; TRY_CAST to DATE happens on load to dw, same as today
    Valor               VARCHAR(50)     NULL,   -- kept as text; TRY_CAST to DECIMAL happens on load to dw
    Categoria_Full      VARCHAR(200)    NULL,
    Descricao           VARCHAR(255)    NULL
);
GO

-- ---------------------------------------------------------------------
-- BLOCK 3 — CONSTRAINTS (added after table creation, per Fabric Warehouse rules)
-- All PRIMARY KEY / FOREIGN KEY here are NOT ENFORCED: informational only,
-- used by the query optimizer and by Power BI to detect relationships —
-- they do NOT physically prevent duplicate keys or orphaned rows.
-- Deduplication/referential integrity remain the responsibility of the
-- stored procedures (Step 3), exactly as today.
-- ---------------------------------------------------------------------

ALTER TABLE dbo.Dim_Calendario
    ADD CONSTRAINT PK_Dim_Calendario PRIMARY KEY NONCLUSTERED (Data) NOT ENFORCED;
GO

ALTER TABLE dbo.FeriadosPT
    ADD CONSTRAINT PK_FeriadosPT PRIMARY KEY NONCLUSTERED (Data) NOT ENFORCED;
GO

ALTER TABLE dw.Dim_Categoria
    ADD CONSTRAINT PK_Dim_Categoria PRIMARY KEY NONCLUSTERED (ID_Categoria) NOT ENFORCED;
GO

ALTER TABLE dw.Fact_Budget
    ADD CONSTRAINT PK_Fact_Budget PRIMARY KEY NONCLUSTERED (ID_Budget) NOT ENFORCED;
GO
ALTER TABLE dw.Fact_Budget
    ADD CONSTRAINT FK_Fact_Budget_Categoria FOREIGN KEY (ID_Categoria)
        REFERENCES dw.Dim_Categoria (ID_Categoria) NOT ENFORCED;
GO

ALTER TABLE dw.Fact_DespesasReais
    ADD CONSTRAINT PK_Fact_DespesasReais PRIMARY KEY NONCLUSTERED (ID_Despesa) NOT ENFORCED;
GO
ALTER TABLE dw.Fact_DespesasReais
    ADD CONSTRAINT FK_Fact_DespesasReais_Categoria FOREIGN KEY (ID_Categoria)
        REFERENCES dw.Dim_Categoria (ID_Categoria) NOT ENFORCED;
GO

ALTER TABLE dw.Fact_Obras
    ADD CONSTRAINT PK_Fact_Obras PRIMARY KEY NONCLUSTERED (ID_Obra) NOT ENFORCED;
GO
ALTER TABLE dw.Fact_Obras
    ADD CONSTRAINT FK_Fact_Obras_Categoria FOREIGN KEY (ID_Categoria)
        REFERENCES dw.Dim_Categoria (ID_Categoria) NOT ENFORCED;
GO

ALTER TABLE dw.Fact_Receitas
    ADD CONSTRAINT PK_Fact_Receitas PRIMARY KEY NONCLUSTERED (ID_Receita) NOT ENFORCED;
GO
ALTER TABLE dw.Fact_Receitas
    ADD CONSTRAINT FK_Fact_Receitas_Categoria FOREIGN KEY (ID_Categoria)
        REFERENCES dw.Dim_Categoria (ID_Categoria) NOT ENFORCED;
GO

ALTER TABLE dw.Fact_Saldos
    ADD CONSTRAINT PK_Fact_Saldos PRIMARY KEY NONCLUSTERED (ID_Saldo) NOT ENFORCED;
GO
ALTER TABLE dw.Fact_Saldos
    ADD CONSTRAINT FK_Fact_Saldos_Categoria FOREIGN KEY (ID_Categoria)
        REFERENCES dw.Dim_Categoria (ID_Categoria) NOT ENFORCED;
GO
