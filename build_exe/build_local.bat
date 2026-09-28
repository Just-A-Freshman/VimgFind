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

rem 自编译的 Tk 8.6.15（修 TTK_STATE_OPEN/user1 映射），见 patch\README.md；
rem 必须盖过 PyInstaller 从 conda 环境拿来的上游版本，否则 Treeview 自定义样式失效
echo === Step 3.5: Patch tk86t.dll ===
if not exist "patch\tk86t.dll" (
    echo MISSING patch\tk86t.dll
    exit /b 1
)
copy /Y "patch\tk86t.dll" "dist\main\_internal\tk86t.dll" >nul
if errorlevel 1 exit /b 1
powershell -NoProfile -Command "$a=(Get-FileHash 'patch\tk86t.dll' -Algorithm MD5).Hash; $b=(Get-FileHash 'dist\main\_internal\tk86t.dll' -Algorithm MD5).Hash; if ($a -ne $b) { Write-Host 'tk86t.dll COPY MISMATCH'; exit 1 } else { Write-Host ('tk86t.dll patched OK ' + $a.Substring(0,12)) }"
if %ERRORLEVEL% neq 0 exit /b 1

echo === Step 4: Verify ===
if not exist "dist\main\main.exe" exit /b 1
echo main.exe OK
rem FileVersion 必须 == WinInfo.version（否则更新脚本判不出/判错版本）
%VIMFIND%\python.exe build_exe\version_utils.py --check dist\main\main.exe
if %ERRORLEVEL% neq 0 exit /b 1
dir /b "dist\main\_internal\config\data"
echo config OK

echo === Step 5: Launch test ===
start /B dist\main\main.exe
%SystemRoot%\System32	imeout.exe /T 15 /NOBREAK >nul
%SystemRoot%\System32	asklist.exe /FI "IMAGENAME eq main.exe" 2>nul | %SystemRoot%\System32ind.exe /I /N "main.exe" >nul
if errorlevel 1 (
    echo LAUNCH FAILED
    taskkill /F /IM main.exe >nul 2>&1
    exit /b 1
)
echo LAUNCH OK
taskkill /F /IM main.exe >nul 2>&1
echo DONE

del main.spec 2>nul
echo === ALL DONE ===