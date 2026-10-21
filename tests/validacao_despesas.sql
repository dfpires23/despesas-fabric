-- =====================================================================
-- Validação da cadeia Copy Data -> 04_ingest_budget -> 02_ingest_despesas
-- =====================================================================

-- 1. A staging deve estar VAZIA (TRUNCATE no fim de sp_ProcessarDespesasReais)
--    Se tiver linhas, algo falhou depois do INSERT em stg mas antes do TRUNCATE.
SELECT COUNT(*) AS Linhas_Staging_Restantes FROM stg.DespesasReais;

-- 2. Quantas despesas reais entraram, por tabela de facto
SELECT 'DespesasReais' AS Tabela, COUNT(*) AS Total FROM dw.Fact_DespesasReais
UNION ALL SELECT 'Obras', COUNT(*) FROM dw.Fact_Obras
UNION ALL SELECT 'Receitas', COUNT(*) FROM dw.Fact_Receitas
UNION ALL SELECT 'Saldos', COUNT(*) FROM dw.Fact_Saldos;

-- 3. Ver os dados reais, com nome de categoria legível (join à Dim)
SELECT TOP 20
    D.Data_Despesa, C.Categoria, C.Subcategoria, D.Valor, D.Descricao,
    D.Notificado_Telegram, D.Telegram_Message_Id
FROM dw.Fact_DespesasReais D
LEFT JOIN dw.Dim_Categoria C ON D.ID_Categoria = C.ID_Categoria
ORDER BY D.Data_Despesa DESC;

-- 4. IMPORTANTE: categorias "órfãs" — criadas automaticamente pela
--    proteção que adicionámos (issue #1 / categoria em falta), porque
--    o valor em Categoria_Full não bateu certo com nada no Budget.
--    Se aparecer alguma linha aqui, vale a pena confirmar se é uma
--    categoria genuinamente nova, ou um erro de escrita no Forms.
SELECT * FROM dw.Dim_Categoria WHERE Natureza IS NULL AND Prioridade IS NULL AND Fonte IS NULL;

-- 5. Confirma que NENHUMA despesa foi notificada por Telegram ainda
--    (o notebook 03_notificar_telegram ainda não corre no pipeline —
--    isto deve dar o mesmo número que o total da query 2, tabela DespesasReais)
SELECT COUNT(*) AS Pendentes_Telegram FROM dw.Fact_DespesasReais WHERE Notificado_Telegram = 0;

-- 6. Se houver despesas de Obras: confirma que também estão pendentes de email
SELECT COUNT(*) AS Pendentes_Email FROM dw.Fact_Obras WHERE Notificado_Email = 0;


-- =====================================================================
-- SECÇÃO 2 — Validação: pipeline completo (6 atividades, incluindo as
-- 3 notificações em paralelo: Telegram, Obras/email, Feriados/Calendário)
-- =====================================================================

-- 7. Depois do pipeline completo, isto deve dar 0 (tudo o que estava
--    pendente de notificação Telegram já foi processado)
SELECT COUNT(*) AS Ainda_Pendentes_Telegram FROM dw.Fact_DespesasReais WHERE Notificado_Telegram = 0
UNION ALL SELECT COUNT(*) FROM dw.Fact_Obras WHERE Notificado_Telegram = 0
UNION ALL SELECT COUNT(*) FROM dw.Fact_Receitas WHERE Notificado_Telegram = 0
UNION ALL SELECT COUNT(*) FROM dw.Fact_Saldos WHERE Notificado_Telegram = 0;

-- 8. Confirma que os Telegram_Message_Id foram mesmo gravados (não ficaram NULL)
SELECT COUNT(*) AS Com_Message_Id FROM dw.Fact_DespesasReais WHERE Telegram_Message_Id IS NOT NULL;

-- 9. Se havia despesas de Obras pendentes, deve estar a 0 agora
SELECT COUNT(*) AS Ainda_Pendentes_Email FROM dw.Fact_Obras WHERE Notificado_Email = 0;

-- 10. Calendário e feriados foram atualizados para o ano atual (2026)
SELECT COUNT(*) AS Dias_Calendario_2026 FROM dbo.Dim_Calendario WHERE Ano = 2026;
SELECT COUNT(*) AS Feriados_2026 FROM dbo.FeriadosPT WHERE YEAR(Data) = 2026;

-- 11. Teste de idempotência: corre o pipeline uma SEGUNDA vez sem
--     alterar o Google Sheet, depois repete a query 2 (contagem por
--     tabela de facto) — os números NÃO devem aumentar. Se aumentarem,
--     a deduplicação por Carimbo_Original não está a funcionar.
