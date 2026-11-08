@echo off
chcp 65001 >nul
setlocal
title Forja de Pergaminhos - instalacao
cd /d "%~dp0"

set "APP=Forja de Pergaminhos"
set "DESTINO=%LOCALAPPDATA%\Programs\%APP%"
set "OBRA=%TEMP%\forja_build"

echo.
echo  ==================================================
echo     FORJA DE PERGAMINHOS - instalacao
echo     Leva uns 5 minutos. Nao feche esta janela.
echo  ==================================================
echo.

rem ---------- 1. Python (so e usado para montar o programa)
call :achar_python
if not defined PY (
    echo  [1/4] Instalando o Python, que e necessario so para montar o programa...
    echo        Se aparecer uma janela pedindo permissao, clique em Sim.
    winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
    set "PY_TEMPORARIO=1"
    call :achar_python
)
if not defined PY (
    echo.
    echo  Nao consegui achar o Python. Baixe em python.org/downloads, instale
    echo  marcando "Add python.exe to PATH" e rode este instalador de novo.
    pause
    exit /b 1
)
echo  Python encontrado: %PY%

rem ---------- 2. Bibliotecas
echo  [1/4] Baixando as pecas do programa...
%PY% -m pip install --disable-pip-version-check -q -r requirements.txt pyinstaller
if errorlevel 1 goto erro

rem ---------- 3. Montar o .exe
echo  [2/4] Forjando o programa (esta e a parte mais demorada)...
if exist "%OBRA%" rmdir /s /q "%OBRA%"
%PY% -m PyInstaller --noconfirm --windowed --log-level ERROR --name "%APP%" ^
  --icon "%~dp0icone.ico" --add-data "%~dp0icone.ico;." --add-data "%~dp0icone.png;." ^
  --collect-all tkinterdnd2 --collect-all pdf2docx ^
  --distpath "%OBRA%\dist" --workpath "%OBRA%\work" --specpath "%OBRA%" ^
  "%~dp0meupdf.py"
if not exist "%OBRA%\dist\%APP%\%APP%.exe" goto erro

rem ---------- 4. Instalar e criar atalhos
echo  [3/4] Instalando em %DESTINO%
taskkill /im "%APP%.exe" /f >nul 2>nul
robocopy "%OBRA%\dist\%APP%" "%DESTINO%" /MIR /NFL /NDL /NJH /NJS /NP >nul
if not exist "%DESTINO%\%APP%.exe" goto erro

echo  [4/4] Criando os icones na Area de Trabalho e no Menu Iniciar...
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$w=New-Object -ComObject WScript.Shell; foreach($p in @([Environment]::GetFolderPath('Desktop'), [Environment]::GetFolderPath('Programs'))){ $s=$w.CreateShortcut($p+'\%APP%.lnk'); $s.TargetPath='%DESTINO%\%APP%.exe'; $s.WorkingDirectory='%DESTINO%'; $s.IconLocation='%DESTINO%\%APP%.exe,0'; $s.Save() }; Remove-Item -ErrorAction SilentlyContinue ([Environment]::GetFolderPath('Desktop')+'\Meu PDF.lnk')"

rmdir /s /q "%OBRA%" >nul 2>nul
if defined PY_TEMPORARIO (
    echo  Removendo o Python, que nao e mais necessario...
    winget uninstall -e --id Python.Python.3.12 --silent >nul 2>nul
)
echo.
echo  ==================================================
echo     Pronto! A Forja de Pergaminhos foi instalada.
echo     Abra pelo icone na Area de Trabalho ou no
echo     Menu Iniciar. Esta pasta pode ser apagada.
echo     O programa funciona sozinho, sem Python.
echo  ==================================================
echo.
start "" "%DESTINO%\%APP%.exe"
pause
exit /b

:achar_python
set "PY="
py -3 -c "import tkinter" >nul 2>nul && set "PY=py -3" && exit /b
python -c "import tkinter" >nul 2>nul && set "PY=python" && exit /b
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*" "%ProgramFiles%\Python3*" "%LOCALAPPDATA%\Python\pythoncore-3*") do (
    if exist "%%~D\python.exe" "%%~D\python.exe" -c "import tkinter" >nul 2>nul && set PY="%%~D\python.exe"
)
exit /b

:erro
echo.
echo  Algo deu errado. Tire um print desta janela e mande para o Claude.
pause
exit /b 1
