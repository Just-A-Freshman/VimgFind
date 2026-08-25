@echo off
chcp 65001 >nul
set VIMFIND=D:\Program_Files\Anaconda\envs\vimgfind
set PATH=%VIMFIND%\Library\bin;%VIMFIND%\Library\usr\bin;%VIMFIND%\Scripts;%VIMFIND%;%PATH%

cd /d "%~dp0.."

echo === Step 1: PyInstaller ===
copy /Y build_exe\main.spec main.spec >nul
%VIMFIND%\python.exe -m PyInstaller main.spec --noconfirm --clean
if %ERRORLEVEL% neq 0 exit /b 1

echo === Step 2: Trim ===
set PYTHONIOENCODING=utf-8
%VIMFIND%\python.exe build_exe\build_trim.py dist\main
if %ERRORLEVEL% neq 0 exit /b 1

echo === Step 3: Copy config ===
if not exist "dist\main\_internal\config" mkdir "dist\main\_internal\config"
xcopy /E /I /Y "build_exe\config\." "dist\main\_internal\config\" >nul

echo === Step 4: Verify ===
if not exist "dist\main\main.exe" exit /b 1
echo main.exe OK
dir /b "dist\main\_internal\config\data"
echo config OK

echo === Step 5: Launch test ===
start /B dist\main\main.exe
timeout /T 15 /NOBREAK >nul
tasklist /FI "IMAGENAME eq main.exe" 2>nul | find /I /N "main.exe" >nul
if errorlevel 1 (
    echo LAUNCH FAILED
    exit /b 1
)
echo LAUNCH OK
taskkill /F /IM main.exe >nul 2>&1
echo DONE

del main.spec 2>nul
echo === ALL DONE ===