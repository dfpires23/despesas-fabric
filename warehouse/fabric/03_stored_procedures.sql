-- GestaoDespesasDW — Fabric Warehouse stored procedures.
-- Differences vs. the SQL Server originals: GENERATE_SERIES instead of a recursive CTE,
-- accent/space-free Dim_Calendario columns, VARCHAR instead of NVARCHAR, explicit
-- Notificado_Telegram = 0 on every INSERT (see docs/fabric-tsql-adaptations.md),
-- and auto-creation of missing categories in sp_ProcessarDespesasReais.
 
-- 1. sp_AtualizarCalendario
CREATE OR ALTER PROCEDURE dbo.sp_AtualizarCalendario
    @AnoInicio INT,
    @AnoFim INT
AS
BEGIN
    TRUNCATE TABLE dbo.Dim_Calendario;
 
    DECLARE @MinDate DATE = DATEFROMPARTS(@AnoInicio, 1, 1);
    DECLARE @MaxDate DATE = DATEFROMPARTS(@AnoFim, 12, 31);
    DECLARE @DataReferencia DATE = CAST(GETDATE() AS DATE);
    DECLARE @DiasTotal INT = DATEDIFF(DAY, @MinDate, @MaxDate);
 
    ;WITH DateSeq AS (
        SELECT DATEADD(DAY, value, @MinDate) AS Data
        FROM GENERATE_SERIES(0, @DiasTotal)
    )
    INSERT INTO dbo.Dim_Calendario (
        Data, Ano, Semestre, SemestreAno, SemestreAnoId,
        Trimestre, TrimestreAno, TrimestreAnoId,
        MesNo, MesLongo, MesCurto, MesAno, MesAnoId,
        DiaDaSemana, DiaDaSemanaNo, TipoDeDia,
        MesRelativo, MesAtual, DiaAtual
    )
    SELECT
        d.Data,
        YEAR(d.Data),
        CASE WHEN MONTH(d.Data) <= 6 THEN 1 ELSE 2 END,
        'S' + CAST(CASE WHEN MONTH(d.Data) <= 6 THEN 1 ELSE 2 END AS VARCHAR) + ' ' + CAST(YEAR(d.Data) AS VARCHAR),
        (YEAR(d.Data) * 10) + CASE WHEN MONTH(d.Data) <= 6 THEN 1 ELSE 2 END,
        DATEPART(Q, d.Data),
        'T' + CAST(DATEPART(Q, d.Data) AS VARCHAR) + ' ' + CAST(YEAR(d.Data) AS VARCHAR),
        (YEAR(d.Data) * 10) + DATEPART(Q, d.Data),
        MONTH(d.Data),
        FORMAT(d.Data, 'MMMM', 'pt-PT'),
        FORMAT(d.Data, 'MMM', 'pt-PT'),
        FORMAT(d.Data, 'yyyy MMM', 'pt-PT'),
        (YEAR(d.Data) * 100) + MONTH(d.Data),
        FORMAT(d.Data, 'dddd', 'pt-PT'),
        DATEPART(WEEKDAY, d.Data),
        CASE WHEN F.Data IS NOT NULL THEN 'Feriado'
             WHEN DATEPART(WEEKDAY, d.Data) IN (1, 7) THEN 'Fim de Semana'
             ELSE 'Dia Útil' END,
        DATEDIFF(MONTH, @DataReferencia, d.Data),
        CASE
            WHEN DATEDIFF(MONTH, @DataReferencia, d.Data) = 0 THEN 'Mês Atual'
            ELSE FORMAT(d.Data, 'yyyy MMM', 'pt-PT')
        END,
        CASE
            WHEN d.Data = @DataReferencia THEN 'Hoje'
            WHEN d.Data = DATEADD(DAY, -1, @DataReferencia) THEN 'Ontem'
            ELSE FORMAT(d.Data, 'dd-MM-yyyy')
        END
    FROM DateSeq AS d
    LEFT JOIN dbo.FeriadosPT F ON d.Data = F.Data;
 
    PRINT 'Calendario Atualizado';
END;
GO
 
-- 2. sp_AtualizarIcones
CREATE OR ALTER PROCEDURE dbo.sp_AtualizarIcones
AS
BEGIN
    DECLARE @Header VARCHAR(50) = 'data:image/svg+xml;utf8, ';
 
    UPDATE dw.Dim_Categoria
    SET Icone_SVG = @Header + CASE Categoria
 
        WHEN 'Alimentação' THEN
            '<svg width=''48'' height=''48'' viewBox=''0 0 48 48'' fill=''none'' xmlns=''http://www.w3.org/2000/svg''><circle cx=''24'' cy=''24'' r=''24'' fill=''#29b6f6''/><path fill-rule=''evenodd'' clip-rule=''evenodd'' d=''M20.8 28.8c-.88 0-1.592.72-1.592 1.6S19.92 32 20.8 32s1.6-.72 1.6-1.6-.72-1.6-1.6-1.6M16 16v1.6h1.6l2.88 6.072-1.08 1.96c-.128.224-.2.488-.2.768 0 .88.72 1.6 1.6 1.6h9.6v-1.6h-9.264a.2.2 0 0 1-.2-.2l.024-.096.72-1.304h5.96c.6 0 1.128-.328 1.4-.824l2.864-5.192A.802.802 0 0 0 31.2 17.6H19.368l-.752-1.6zm12.8 12.8c-.88 0-1.592.72-1.592 1.6S27.92 32 28.8 32s1.6-.72 1.6-1.6-.72-1.6-1.6-1.6'' fill=''#fff''/></svg>'
 
        WHEN 'Habitação' THEN
            '<svg width=''48'' height=''48'' viewBox=''0 0 48 48'' fill=''none'' xmlns=''http://www.w3.org/2000/svg''><circle cx=''24'' cy=''24'' r=''24'' fill=''#ffa726''/><path fill-rule=''evenodd'' clip-rule=''evenodd'' d=''M22.2 32v-5.294h3.6V32h4.5v-7.059H33L24 17l-9 7.941h2.7V32z'' fill=''#fff''/></svg>'
 
        WHEN 'Transporte' THEN
            '<svg width=''48'' height=''48'' viewBox=''0 0 48 48'' fill=''none'' xmlns=''http://www.w3.org/2000/svg''><circle cx=''24'' cy=''24'' r=''24'' fill=''#ab47bc''/><path d=''M30.92 17.01c-.2-.59-.76-1.01-1.42-1.01h-11c-.66 0-1.21.42-1.42 1.01L15 23v8c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-1h12v1c0 .55.45 1 1 1h1c.55 0 1-.45 1-1v-8zM18.5 27c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5m11 0c-.83 0-1.5-.67-1.5-1.5s.67-1.5 1.5-1.5 1.5.67 1.5 1.5-.67 1.5-1.5 1.5M17 22l1.5-4.5h11L31 22z'' fill=''#fff''/></svg>'
 
        WHEN 'Saúde' THEN
            '<svg width=''48'' height=''48'' viewBox=''0 0 48 48'' fill=''none'' xmlns=''http://www.w3.org/2000/svg''><circle cx=''24'' cy=''24'' r=''24'' fill=''#ef5350''/><path d=''M31.943 24.412a.6.6 0 0 0-.514-.285c-1.254 0-2.452.57-3.194 1.597l-.513.684c-.628.742-1.597 1.141-2.567 1.141h-1.711c-.342 0-.57-.228-.57-.57 0-.343.228-.57.57-.57h1.084c.912 0 1.768-.742 1.768-1.655v-.057c0-.285-.285-.57-.57-.57h-3.48c-2.053 0-3.708.912-4.62 2.395l-1.54 2.396a.52.52 0 0 0 0 .57l1.71 2.853c.058.114.229.228.343.285h.114c.114 0 .228-.057.342-.114a13.15 13.15 0 0 1 7.245-2.168 5.14 5.14 0 0 0 4.506-2.68l1.54-2.739c.114-.114.114-.342.057-.513'' fill=''#fff''/><path d=''M22.246 22.986h3.48c.912 0 1.71.741 1.71 1.654v.114l3.537-3.65a3.65 3.65 0 0 0 0-5.077C30.29 15.399 29.433 15 28.521 15c-.913 0-1.826.4-2.51 1.084l-.285.285-.286-.285C24.756 15.399 23.9 15 22.93 15c-.912 0-1.768.4-2.452 1.084a3.65 3.65 0 0 0 0 5.076zm.628-3.423h.912l.97-.97q.171-.17.513-.17c.171.057.343.17.4.285l.57 1.14.684-1.654a.5.5 0 0 1 .457-.342c.228 0 .4.057.513.228l1.141 1.712c.171.285.114.627-.171.798s-.628.114-.799-.171l-.513-.799-.742 1.826a.55.55 0 0 1-.513.399q-.343 0-.513-.342l-.799-1.597-.57.57c-.114.171-.229.228-.4.228h-1.14c-.343 0-.57-.228-.57-.57 0-.343.227-.57.57-.57'' fill=''#fff''/></svg>'
 
        WHEN 'Educação' THEN
            '<svg width=''48'' height=''48'' viewBox=''0 0 48 48'' fill=''none'' xmlns=''http://www.w3.org/2000/svg''><circle cx=''24'' cy=''24'' r=''24'' fill=''#ba68c8''/><path d=''M31.695 25.02s-3.053-3.061-7.259-3.061c-4.11 0-8.172 3.062-8.172 3.062l-2.282-.937v2.75a.89.89 0 0 1 .623.84.89.89 0 0 1-.633.842l.674 1.852h-1.991l.68-1.868a.9.9 0 0 1-.555-.826c0-.365.222-.675.539-.816v-3.047L10 22.449 24.603 16 38 22.53zm-7.425-1.51c4.232 0 6.305 2.204 6.305 2.204v4.572S28.42 32 23.94 32s-5.974-1.714-5.974-1.714v-4.572s2.074-2.204 6.305-2.204m-.083 7.51c2.933 0 5.31-.585 5.31-1.306 0-.72-2.377-1.306-5.31-1.306s-5.31.585-5.31 1.306c0 .72 2.378 1.306 5.31 1.306'' fill=''#fff''/></svg>'
 
        WHEN 'Lazer' THEN
            '<svg width=''48'' height=''48'' viewBox=''0 0 48 48'' fill=''none'' xmlns=''http://www.w3.org/2000/svg''><circle cx=''24'' cy=''24'' r=''24'' fill=''#66bb6a''/><path fill-rule=''evenodd'' clip-rule=''evenodd'' d=''M24 15c-4.968 0-9 4.032-9 9s4.032 9 9 9 9-4.032 9-9-4.032-9-9-9m-1.8 13.05v-8.1L27.6 24z'' fill=''#fff''/></svg>'
 
        WHEN 'Administrativas' THEN
            '<svg width=''48'' height=''48'' viewBox=''0 0 48 48'' fill=''none'' xmlns=''http://www.w3.org/2000/svg''><circle cx=''24'' cy=''24'' r=''24'' fill=''#607d8b''/><path d=''m25.33 14-.353.023-.348.06-.337.1-.327.137-.308.172-.286.206-.262.237-.234.266-.202.288-.17.311h-.778l-.425.9h.932l-.03.3v.3l.03.3h-.507l-.425.9h1.202l.17.311.203.288.234.266.262.237.286.206.308.174.327.135.337.1.348.064.354.019.353-.016.348-.058.34-.096.328-.132-.387-.814-.288.11-.297.076-.306.03-.31-.012-.303-.053-.292-.093-.278-.136-.258-.168-.23-.204-.203-.234h1.61l.427-.9h-2.441l-.039-.3V17l.039-.3h2.42l.426-.9h-2.442l.202-.234.23-.204.26-.168.277-.136.292-.093.304-.053.31-.012.305.03.297.075.288.111.387-.812-.329-.133-.339-.097-.348-.056zm-4.93 3.816L15 19.52v2.58h.9v7.2H15V32h18v-2.7h-.9v-7.2h.9v-2.58l-5.4-1.704v.942l4.5 1.422v1.02H15.9v-1.021l4.5-1.42zM16.8 22.1h.9v7.2h-.9zm1.8 0h1.8v7.2h-1.8zm2.7 0h.9v7.2h-.9zm1.8 0h1.8v7.2h-1.8zm2.7 0h.9v7.2h-.9zm1.8 0h1.8v7.2h-1.8zm2.7 0h.9v7.2h-.9zm-14.4 8.1h16.2v.9H15.9z'' fill=''#fff''/></svg>'
 
        WHEN 'Outros' THEN
            '<svg width=''48'' height=''48'' viewBox=''0 0 48 48'' fill=''none'' xmlns=''http://www.w3.org/2000/svg''><circle cx=''24'' cy=''24'' r=''24'' fill=''#009688''/><path d=''m32.82 19.517-.006-.011q0-.002-.003-.005a1.33 1.33 0 0 0-.517-.46L24.68 15.16A1.5 1.5 0 0 0 24 15c-.238 0-.471.055-.679.16l-7.615 3.88a1.33 1.33 0 0 0-.518.464l-.005.006-.005.01a1.16 1.16 0 0 0-.178.613v7.733c0 .222.066.44.19.633.124.192.302.35.516.46l7.615 3.88c.192.097.407.151.626.158l.048.003H24l.065-.003a1.5 1.5 0 0 0 .613-.158l7.615-3.88c.214-.11.392-.268.516-.46s.19-.41.19-.633v-7.733c0-.216-.062-.428-.18-.616M24 16.253l6.9 3.516-2.649 1.364-6.982-3.488zm.079 7.027-6.97-3.516 2.74-1.396 6.99 3.492zm.624 8.108.068-7.022 2.779-1.43v2.985c0 .166.073.326.203.443a.73.73 0 0 0 .49.184.73.73 0 0 0 .489-.184.6.6 0 0 0 .203-.443v-3.697l2.68-1.38v7.022z'' fill=''#fff''/></svg>'
 
        ELSE NULL
    END;
 
    PRINT 'Ícones atualizados na Dimensão Categoria.';
END;
GO
 
-- 3. sp_ProcessarBudget
CREATE OR ALTER PROCEDURE dbo.sp_ProcessarBudget
AS
BEGIN
    -- 1. Insert new categories (if they do not exist)
    INSERT INTO dw.Dim_Categoria (Categoria, Subcategoria, Natureza, Prioridade, Fonte)
    SELECT DISTINCT
        S.Categoria,
        S.Subcategoria,
        S.Natureza,
        S.Prioridade,
        S.Fonte
    FROM stg.Budget S
    WHERE NOT EXISTS (
        SELECT 1 FROM dw.Dim_Categoria D
        WHERE D.Categoria = S.Categoria AND D.Subcategoria = S.Subcategoria
    );
 
    -- 2. Update attributes of existing categories (SCD1; SCD2 planned, see data-governance-notes.md)
    UPDATE D
    SET
        D.Natureza = S.Natureza,
        D.Prioridade = S.Prioridade,
        D.Fonte = S.Fonte
    FROM dw.Dim_Categoria D
    INNER JOIN stg.Budget S
        ON D.Categoria = S.Categoria AND D.Subcategoria = S.Subcategoria;
 
    -- 3. Load facts (keys and values only)
    TRUNCATE TABLE dw.Fact_Budget;
 
    INSERT INTO dw.Fact_Budget (ID_Categoria, Data_Referencia, Valor)
    SELECT
        DC.ID_Categoria,
        DATEFROMPARTS(B.Ano,
            CASE LEFT(B.Mes, 3)
                WHEN 'Jan' THEN 1 WHEN 'Fev' THEN 2 WHEN 'Mar' THEN 3
                WHEN 'Abr' THEN 4 WHEN 'Mai' THEN 5 WHEN 'Jun' THEN 6
                WHEN 'Jul' THEN 7 WHEN 'Ago' THEN 8 WHEN 'Set' THEN 9
                WHEN 'Out' THEN 10 WHEN 'Nov' THEN 11 WHEN 'Dez' THEN 12
                ELSE 1 END, 1),
        B.Valor
    FROM stg.Budget AS B
    INNER JOIN dw.Dim_Categoria AS DC
        ON B.Categoria = DC.Categoria AND B.Subcategoria = DC.Subcategoria;
 
    -- 4. Cleanup
    TRUNCATE TABLE stg.Budget;
    EXEC dbo.sp_AtualizarIcones;
END;
GO
 
-- 4. sp_ProcessarDespesasReais
CREATE OR ALTER PROCEDURE dbo.sp_ProcessarDespesasReais
AS
BEGIN
    -- 0. Automatically create missing categories so no expense is discarded.
    --    Nature/Priority/Source remain NULL until the next Budget.
    INSERT INTO dw.Dim_Categoria (Categoria, Subcategoria, Natureza, Prioridade, Fonte, Icone_SVG)
    SELECT DISTINCT
        LEFT(S.Categoria_Full, CHARINDEX(' - ', S.Categoria_Full + ' - ') - 1) AS Categoria,
        NULLIF(SUBSTRING(S.Categoria_Full, CHARINDEX(' - ', S.Categoria_Full + ' - ') + 3, 200), '') AS Subcategoria,
        NULL, NULL, NULL, NULL
    FROM stg.DespesasReais S
    WHERE S.Categoria_Full IS NOT NULL
      AND NOT EXISTS (
        SELECT 1 FROM dw.Dim_Categoria D
        WHERE (D.Categoria + ' - ' + D.Subcategoria) = S.Categoria_Full
      );
 
    -- 1. Insert OBRAS
    INSERT INTO dw.Fact_Obras (ID_Categoria, Data_Despesa, Valor, Descricao, Carimbo_Original, Notificado_Telegram, Telegram_Message_Id, Notificado_Email)
    SELECT
        DC.ID_Categoria,
        TRY_CAST(STG.Data_Despesa AS DATE),
        TRY_CAST(STG.Valor AS DECIMAL(18,2)),
        STG.Descricao,
        STG.Carimbo,
        0,
        NULL,
        0
    FROM stg.DespesasReais AS STG
    LEFT JOIN dw.Dim_Categoria AS DC ON STG.Categoria_Full = (DC.Categoria + ' - ' + DC.Subcategoria)
    WHERE DC.Categoria = 'Obras'
      AND NOT EXISTS (SELECT 1 FROM dw.Fact_Obras F WHERE F.Carimbo_Original = STG.Carimbo);
 
    -- 2. Insert RECEITAS
    INSERT INTO dw.Fact_Receitas (ID_Categoria, Data_Receita, Valor, Descricao, Carimbo_Original, Notificado_Telegram, Telegram_Message_Id)
    SELECT
        DC.ID_Categoria,
        TRY_CAST(STG.Data_Despesa AS DATE),
        TRY_CAST(STG.Valor AS DECIMAL(18,2)),
        STG.Descricao,
        STG.Carimbo,
        0,
        NULL
    FROM stg.DespesasReais AS STG
    LEFT JOIN dw.Dim_Categoria AS DC ON STG.Categoria_Full = (DC.Categoria + ' - ' + DC.Subcategoria)
    WHERE DC.Categoria = 'Receitas'
      AND NOT EXISTS (SELECT 1 FROM dw.Fact_Receitas F WHERE F.Carimbo_Original = STG.Carimbo);
 
    -- 3. Insert SALDOS
    INSERT INTO dw.Fact_Saldos (ID_Categoria, Data_Saldo, Valor, Descricao, Carimbo_Original, Notificado_Telegram, Telegram_Message_Id)
    SELECT
        DC.ID_Categoria,
        TRY_CAST(STG.Data_Despesa AS DATE),
        TRY_CAST(STG.Valor AS DECIMAL(18,2)),
        STG.Descricao,
        STG.Carimbo,
        0,
        NULL
    FROM stg.DespesasReais AS STG
    LEFT JOIN dw.Dim_Categoria AS DC ON STG.Categoria_Full = (DC.Categoria + ' - ' + DC.Subcategoria)
    WHERE DC.Categoria = 'Saldos'
      AND NOT EXISTS (SELECT 1 FROM dw.Fact_Saldos F WHERE F.Carimbo_Original = STG.Carimbo);
 
    -- 4. Insert DESPESAS REAIS (everything else, excluding Obras/Receitas/Saldos)
    INSERT INTO dw.Fact_DespesasReais (ID_Categoria, Data_Despesa, Valor, Descricao, Carimbo_Original, Notificado_Telegram, Telegram_Message_Id)
    SELECT
        DC.ID_Categoria,
        TRY_CAST(STG.Data_Despesa AS DATE),
        TRY_CAST(STG.Valor AS DECIMAL(18,2)),
        STG.Descricao,
        STG.Carimbo,
        0,
        NULL
    FROM stg.DespesasReais AS STG
    LEFT JOIN dw.Dim_Categoria AS DC ON STG.Categoria_Full = (DC.Categoria + ' - ' + DC.Subcategoria)
    WHERE DC.Categoria NOT IN ('Receitas', 'Obras', 'Saldos')
      AND NOT EXISTS (SELECT 1 FROM dw.Fact_DespesasReais F WHERE F.Carimbo_Original = STG.Carimbo);
 
    -- 5. Clear staging
    TRUNCATE TABLE stg.DespesasReais;
END;
GO
 