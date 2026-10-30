-- Email outbox flag for dw.Fact_Obras (the only table that triggers an email report).
-- Must be NULLable (Fabric rejects NOT NULL on ALTER ADD); sp_ProcessarDespesasReais writes 0 on every INSERT.
-- Run once after 01_create_schemas_and_tables.sql.
ALTER TABLE dw.Fact_Obras
    ADD Notificado_Email BIT NULL;
GO
 