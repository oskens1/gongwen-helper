@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Build EXE v17
echo ============================================
echo   Build gongwen helper v17  (clean rebuild)
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

rem === Locate v17 main script by wildcard (keep this bat pure ASCII) ===
set "MAINPY="
for %%f in ("%~dp0*_v17.py") do if not defined MAINPY set "MAINPY=%%f"
if not defined MAINPY echo ERROR: *_v17.py not found in this folder. & pause & exit /b 1
echo Main script: %MAINPY%
echo.

rem === Kill running instance so exe can be overwritten ===
taskkill /F /IM gongwen_helper.exe >nul 2>&1

rem === Delete old output so a stale exe cannot fake success ===
if exist "%TEMP%\gw_build_v17" rmdir /S /Q "%TEMP%\gw_build_v17"

echo [1/6] Installing pinned app deps (requirements.txt) + PyInstaller ...
"%PYTHON%" -m pip install --upgrade pyinstaller
if exist "requirements.txt" "%PYTHON%" -m pip install -r requirements.txt
echo.
echo [2/6] Force-reinstall lxml (bundled-DLL wheel) ...
"%PYTHON%" -m pip install --upgrade --force-reinstall --only-binary :all: lxml
echo.
echo [3/6] Building ... (full log -> build_log.txt, please wait 1-3 min)
set ICONARG=
if exist "icon.ico" set ICONARG=--icon "icon.ico" --add-data "icon.ico;."
set SPLASHARG=
if exist "splash.png" set SPLASHARG=--splash "splash.png"
"%PYTHON%" -m PyInstaller --noconfirm --clean --windowed --onedir --noupx ^
  --collect-all DrissionPage --collect-all pdfminer --collect-all pdfplumber ^
  --exclude-module numpy --exclude-module pandas --exclude-module matplotlib ^
  --exclude-module scipy --exclude-module IPython --exclude-module PyQt5 ^
  --exclude-module PyQt6 --exclude-module PySide2 --exclude-module PySide6 ^
  --exclude-module notebook --exclude-module torch --exclude-module torchvision ^
  --exclude-module torchaudio --exclude-module tensorflow --exclude-module transformers ^
  --exclude-module cv2 --exclude-module sklearn --exclude-module numba ^
  --exclude-module llvmlite --exclude-module sympy --exclude-module whisper ^
  %ICONARG% %SPLASHARG% --name "gongwen_helper" ^
  --workpath "%TEMP%\gw_work_v17" --distpath "%TEMP%\gw_build_v17" "%MAINPY%" > "%~dp0build_log.txt" 2>&1
echo.

set "DEST=%TEMP%\gw_build_v17\gongwen_helper\_internal"

echo [4/6] Copy Anaconda DLLs (ONLY when building with Anaconda) ...
if not defined ISANACONDA echo    Non-Anaconda build - skipping Anaconda DLLs. & goto :skipana
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
:skipana
echo.
echo [5/6] Bundle VC++ runtime + UCRT (so it runs on PCs without VC redist) ...
copy /Y "%SystemRoot%\System32\VCRUNTIME140.dll"      "%DEST%\" >nul 2>&1
copy /Y "%SystemRoot%\System32\VCRUNTIME140_1.dll"    "%DEST%\" >nul 2>&1
copy /Y "%SystemRoot%\System32\msvcp140.dll"          "%DEST%\" >nul 2>&1
copy /Y "%SystemRoot%\System32\msvcp140_1.dll"        "%DEST%\" >nul 2>&1
copy /Y "%SystemRoot%\System32\ucrtbase.dll"          "%DEST%\" >nul 2>&1
copy /Y "%SystemRoot%\System32\api-ms-win-crt-*.dll"  "%DEST%\" >nul 2>&1
copy /Y "%SystemRoot%\System32\api-ms-win-core-*.dll" "%DEST%\" >nul 2>&1
echo    VC++ runtime + UCRT bundled.
echo.

set "OUTEXE=%TEMP%\gw_build_v17\gongwen_helper\gongwen_helper.exe"
if not exist "%OUTEXE%" goto :buildfail

echo [6/6] Bundle Tcl/Tk data from project tkdata (known-good v16 copy) ...
xcopy /E /I /Y /Q "%~dp0tkdata\_tcl_data" "%DEST%\_tcl_data\" >nul 2>&1
xcopy /E /I /Y /Q "%~dp0tkdata\_tk_data"  "%DEST%\_tk_data\"  >nul 2>&1
if exist "%DEST%\_tk_data\tk.tcl" (echo    Tcl/Tk data OK ^(tk.tcl present^).) else (echo    [WARN] tk.tcl MISSING - check that tkdata folder exists next to this bat!)
echo.

if exist "使用說明_請先看我.txt" copy /Y "使用說明_請先看我.txt" "%TEMP%\gw_build_v17\gongwen_helper\" >nul 2>&1
if exist "讀我.md" copy /Y "讀我.md" "%TEMP%\gw_build_v17\gongwen_helper\" >nul 2>&1
echo ============================================
echo   BUILD OK. Output (auto-opening):
echo   %TEMP%\gw_build_v17\gongwen_helper\
echo   Run gongwen_helper.exe
echo ============================================
explorer "%TEMP%\gw_build_v17\gongwen_helper"
pause
exit /b 0
:buildfail
echo ============================================
echo   BUILD FAILED: exe not produced. See build_log.txt.
echo ============================================
pause
exit /b 1
