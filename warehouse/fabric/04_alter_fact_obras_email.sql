-- =====================================================================
-- Adds an email-outbox column to dw.Fact_Obras, mirroring the
-- Notificado_Telegram pattern already used across the fact tables
-- (see architecture.md §5). Only Fact_Obras needs this — it's the only
-- table that triggers an email report.
--
-- Run this once against GestaoDespesasDW.
-- =====================================================================

-- NOTE: Fabric Warehouse only allows adding NULLable columns via
-- ALTER TABLE (NOT NULL is rejected — Msg 24735 "Only nullable columns
-- can be added to an existing table"). The stored procedure already
-- writes 0 explicitly on every INSERT (same reasoning as the other
-- Notificado_Telegram columns — no DEFAULT support either), so this is
-- functionally equivalent even without a NOT NULL constraint enforcing it.
ALTER TABLE dw.Fact_Obras
    ADD Notificado_Email BIT NULL;
GO
