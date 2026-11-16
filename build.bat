@echo off
:: ============================================================
::  BioMotion – Pipeline completo de build
::  Passo 1: PyInstaller → dist\BioMotion\
::  Passo 2: Inno Setup  → installer\BioMotion_Instalador_v2.2.exe
:: ============================================================
title BioMotion Build Pipeline
setlocal

set INNO="C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
set ISS=BioMotion_Setup.iss

echo.
echo  ================================================
echo   BioMotion - Pipeline de Compilacao
echo  ================================================
echo.

:: ── Passo 0: Verificações ────────────────────────────────────
if not exist .venv\Scripts\activate.bat (
    echo [ERRO] Ambiente virtual nao encontrado em .venv\
    echo        Execute: python -m venv .venv
    pause & exit /b 1
)

:: ── Passo 1: PyInstaller ────────────────────────────────────
echo [1/2] Compilando com PyInstaller...
call .venv\Scripts\activate.bat

if exist build  rmdir /s /q build
if exist dist   rmdir /s /q dist

pyinstaller BioMotion.spec --noconfirm
if errorlevel 1 (
    echo.
    echo [ERRO] PyInstaller falhou. Verifique as mensagens acima.
    pause & exit /b 1
)

:: Garante que a pasta de sessoes existe no dist
if not exist dist\BioMotion\Analises_Salvas (
    mkdir dist\BioMotion\Analises_Salvas
)

echo.
echo  [OK] Executavel gerado: dist\BioMotion\BioMotion.exe
echo.

:: ── Passo 2: Inno Setup ─────────────────────────────────────
echo [2/2] Criando instalador com Inno Setup...

if not exist %INNO% (
    echo.
    echo  [AVISO] Inno Setup nao encontrado em:
    echo          C:\Program Files ^(x86^)\Inno Setup 6\
    echo.
    echo  Para criar o instalador .exe:
    echo    1. Acesse: https://jrsoftware.org/isdl.php
    echo    2. Baixe e instale o Inno Setup 6
    echo    3. Execute este build.bat novamente
    echo.
    echo  Por ora, distribua a pasta: dist\BioMotion\  ^(zipada^)
    echo.
    pause & exit /b 0
)

if not exist installer mkdir installer

%INNO% %ISS%
if errorlevel 1 (
    echo.
    echo [ERRO] Inno Setup falhou. Verifique BioMotion_Setup.iss
    pause & exit /b 1
)

echo.
echo  ================================================
echo   BUILD COMPLETO!
echo.
echo   Executavel standalone:
echo     dist\BioMotion\BioMotion.exe
echo.
echo   Instalador unico (distribuir este):
echo     installer\BioMotion_Instalador_v2.2.exe
echo  ================================================
echo.
pause
