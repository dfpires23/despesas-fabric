-- GestaoDespesasDW — Fabric Warehouse DDL.
-- Drops and recreates every table: do NOT re-run once real data exists.
-- Run 04_alter_fact_obras_email.sql afterwards (adds Fact_Obras.Notificado_Email).
-- Fabric T-SQL rules applied here: see docs/fabric-tsql-adaptations.md.
 
-- Cleanup
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
 
-- Schemas ('dbo' exists by default)
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'dw')
    EXEC('CREATE SCHEMA dw');
GO
IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'stg')
    EXEC('CREATE SCHEMA stg');
GO
 
-- Tables: calendar and holidays
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
 
-- Tables: dimensional model
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
 
-- Fact tables below: Notificado_Telegram must be set to 0 by every INSERT (no DEFAULT in Fabric)
CREATE TABLE dw.Fact_DespesasReais (
    ID_Despesa          BIGINT IDENTITY NOT NULL,
    ID_Categoria        BIGINT          NOT NULL,
    Data_Despesa        DATE            NULL,
    Valor               DECIMAL(10,2)   NULL,
    Descricao           VARCHAR(255)    NULL,
    Carimbo_Original    VARCHAR(100)    NULL,
    Notificado_Telegram BIT             NOT NULL,
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
 
-- Tables: staging (text columns are cast on load to dw)
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
    Data_Despesa        VARCHAR(50)     NULL,
    Valor               VARCHAR(50)     NULL,
    Categoria_Full      VARCHAR(200)    NULL,
    Descricao           VARCHAR(255)    NULL
);
GO
 
-- Constraints: NOT ENFORCED (informational only, used by the optimizer and Power BI).
-- Deduplication and referential integrity are handled by the stored procedures.
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
 