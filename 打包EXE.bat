@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Build EXE v16
echo ============================================
echo   Build gongwen helper v16  (clean rebuild)
echo ============================================
echo.

rem === Auto-detect Python: py -> python -> Anaconda ===
set "PYTHON="
set "ISANACONDA="
where py >nul 2>nul && set "PYTHON=py"
if defined PYTHON goto :gotpy
where python >nul 2>nul && set "PYTHON=python"
if defined PYTHON goto :gotpy
if exist "%USERPROFILE%\anaconda3\python.exe" set "PYTHON=%USERPROFILE%\anaconda3\python.exe" & set "ISANACONDA=1"
if defined PYTHON goto :gotpy
echo ERROR: No Python found (tried py, python, Anaconda). & pause & exit /b 1
:gotpy
echo Using Python: %PYTHON%
"%PYTHON%" --version
echo.

rem === Kill running instance so exe can be overwritten ===
taskkill /F /IM gongwen_helper.exe >nul 2>&1
taskkill /F /IM "公文小助手.exe" >nul 2>&1

rem === Delete old output so a stale exe cannot fake success ===
if exist "%TEMP%\gw_build_v16" rmdir /S /Q "%TEMP%\gw_build_v16"

echo [1/4] Upgrading PyInstaller + app deps in THIS Python ...
"%PYTHON%" -m pip install --upgrade pyinstaller DrissionPage pdfplumber pillow
echo.
echo [2/4] Force-reinstall lxml (bundled-DLL wheel) ...
"%PYTHON%" -m pip install --upgrade --force-reinstall --only-binary :all: lxml
echo.
echo [3/4] Building ... (full log -> build_log.txt, please wait 1-3 min)
set ICONARG=
if exist "icon.ico" set ICONARG=--icon "icon.ico" --add-data "icon.ico;."
set SPLASHARG=
if exist "splash.png" set SPLASHARG=--splash "splash.png"
"%PYTHON%" -m PyInstaller --noconfirm --clean --windowed --onedir --noupx --collect-all DrissionPage --exclude-module numpy --exclude-module pandas --exclude-module matplotlib --exclude-module scipy --exclude-module IPython --exclude-module PyQt5 --exclude-module PyQt6 --exclude-module PySide2 --exclude-module PySide6 --exclude-module notebook %ICONARG% %SPLASHARG% --name "gongwen_helper" --workpath "%TEMP%\gw_work_v16" --distpath "%TEMP%\gw_build_v16" "公文小助手_v16.py" > "%~dp0build_log.txt" 2>&1
echo.
echo [4/4] Copy Anaconda DLLs (ONLY when building with Anaconda) ...
if not defined ISANACONDA echo    Standard Python build - skipping. & goto :skipdll
set "DEST=%TEMP%\gw_build_v16\gongwen_helper\_internal"
set "ABIN=%USERPROFILE%\anaconda3\Library\bin"
set "ADLL=%USERPROFILE%\anaconda3\DLLs"
copy /Y "%ABIN%\tcl86*.dll" "%DEST%\" >nul 2>&1
copy /Y "%ABIN%\tk86*.dll"  "%DEST%\" >nul 2>&1
copy /Y "%ABIN%\zlib*.dll"  "%DEST%\" >nul 2>&1
copy /Y "%ABIN%\sqlite3.dll" "%DEST%\" >nul 2>&1
copy /Y "%ADLL%\sqlite3.dll" "%DEST%\" >nul 2>&1
copy /Y "%ABIN%\libssl*.dll"    "%DEST%\" >nul 2>&1
copy /Y "%ABIN%\libcrypto*.dll" "%DEST%\" >nul 2>&1
copy /Y "%ABIN%\ffi*.dll"     "%DEST%\" >nul 2>&1
copy /Y "%ABIN%\libffi*.dll"  "%DEST%\" >nul 2>&1
copy /Y "%ABIN%\liblzma*.dll" "%DEST%\" >nul 2>&1
copy /Y "%ABIN%\libbz2*.dll"  "%DEST%\" >nul 2>&1
echo    Anaconda DLLs copied.
:skipdll
echo.
set "OUTEXE=%TEMP%\gw_build_v16\gongwen_helper\gongwen_helper.exe"
if not exist "%OUTEXE%" goto :buildfail
copy /Y "使用說明_請先看我.txt" "%TEMP%\gw_build_v16\gongwen_helper\" >nul 2>&1
echo ============================================
echo   BUILD OK. Output (auto-opening):
echo   %TEMP%\gw_build_v16\gongwen_helper\
echo   Run gongwen_helper.exe
echo ============================================
explorer "%TEMP%\gw_build_v16\gongwen_helper"
pause
exit /b 0
:buildfail
echo ============================================
echo   BUILD FAILED: exe not produced. See build_log.txt.
echo ============================================
pause
exit /b 1
