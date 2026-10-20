@echo off
:: 1. Garante que estamos na pasta correta (onde está este ficheiro)
cd /d "%~dp0"

:: 2. Ativa o ambiente virtual (ajusta 'venv' se a tua pasta tiver outro nome)
call .venv\Scripts\activate

:: 3. Corre o script Mestre
python etl_master.py

:: 4. Pausa no fim para veres se deu erro ou sucesso antes de fechar
echo.
echo --- FIM DA EXECUCAO ---
pause