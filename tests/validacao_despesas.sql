-- Pipeline validation (GestaoDespesasDW). Run after a complete execution.

-- 1. Staging should be empty (otherwise, it failed between the INSERT into stg and the TRUNCATE)
SELECT COUNT(*) AS Linhas_Staging_Restantes FROM stg.DespesasReais;

-- 2. Total row count per fact table
SELECT 'DespesasReais' AS Tabela, COUNT(*) AS Total FROM dw.Fact_DespesasReais
UNION ALL SELECT 'Obras', COUNT(*) FROM dw.Fact_Obras
UNION ALL SELECT 'Receitas', COUNT(*) FROM dw.Fact_Receitas
UNION ALL SELECT 'Saldos', COUNT(*) FROM dw.Fact_Saldos;

-- 3. Latest expenses, with category name
SELECT TOP 20
    D.Data_Despesa, C.Categoria, C.Subcategoria, D.Valor, D.Descricao,
    D.Notificado_Telegram, D.Telegram_Message_Id
FROM dw.Fact_DespesasReais D
LEFT JOIN dw.Dim_Categoria C ON D.ID_Categoria = C.ID_Categoria
ORDER BY D.Data_Despesa DESC;

-- 4. Auto-created categories (without a match in Budget): confirm whether they are new or a Forms entry error
SELECT * FROM dw.Dim_Categoria WHERE Natureza IS NULL AND Prioridade IS NULL AND Fonte IS NULL;

-- 5. Telegram pending items per table (0 after notebook 03 runs)
SELECT COUNT(*) AS Ainda_Pendentes_Telegram FROM dw.Fact_DespesasReais WHERE Notificado_Telegram = 0
UNION ALL SELECT COUNT(*) FROM dw.Fact_Obras WHERE Notificado_Telegram = 0
UNION ALL SELECT COUNT(*) FROM dw.Fact_Receitas WHERE Notificado_Telegram = 0
UNION ALL SELECT COUNT(*) FROM dw.Fact_Saldos WHERE Notificado_Telegram = 0;

-- 6. Stored Telegram_Message_Id (not NULL)
SELECT COUNT(*) AS Com_Message_Id FROM dw.Fact_DespesasReais WHERE Telegram_Message_Id IS NOT NULL;

-- 7. Pending email notifications for Works (0 after notebook 05 runs)
SELECT COUNT(*) AS Ainda_Pendentes_Email FROM dw.Fact_Obras WHERE Notificado_Email = 0;

-- 8. Calendar and holidays for the current year (adjust the year)
SELECT COUNT(*) AS Dias_Calendario_2026 FROM dbo.Dim_Calendario WHERE Ano = 2026;
SELECT COUNT(*) AS Feriados_2026 FROM dbo.FeriadosPT WHERE YEAR(Data) = 2026;

-- 9. Idempotency: run the pipeline a second time without changing the Google Sheet and repeat query 2.
--    The totals should not increase (otherwise, deduplication by Carimbo_Original failed).