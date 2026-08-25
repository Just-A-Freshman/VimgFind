<#
.SYNOPSIS
    本地执行完整构建流程，与 CI (build-win.yml) 一致。
    需要 conda activate vimgfind 环境。
#>

$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "=== 步骤1: PyInstaller 打包 ===" -ForegroundColor Cyan
Copy-Item build_exe/main.spec main.spec -Force
pyinstaller main.spec --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 失败" }

Write-Host "`n=== 步骤2: 裁剪 dist ===" -ForegroundColor Cyan
$env:PYTHONIOENCODING = "utf-8"
python build_exe/build_trim.py dist/main
if ($LASTEXITCODE -ne 0) { throw "裁剪失败" }

Write-Host "`n=== 步骤3: 移动 config 到 _internal ===" -ForegroundColor Cyan
if (-not (Test-Path "dist/main/_internal/config")) { New-Item -ItemType Directory -Path "dist/main/_internal/config" -Force | Out-Null }
Copy-Item -Recurse -Force "build_exe/config/*" "dist/main/_internal/config/"

Write-Host "`n=== 步骤4: 验证构建产物 ===" -ForegroundColor Cyan
if (-not (Test-Path "dist/main/main.exe")) { throw "main.exe 未生成" }
Write-Host "  OK main.exe 已生成"
Get-ChildItem "dist/main/_internal/config/data"
Write-Host "  OK config 已移动到 _internal/"

Write-Host "`n=== 步骤5: 启动测试 ===" -ForegroundColor Cyan
$proc = Start-Process -FilePath "dist/main/main.exe" -WindowStyle Hidden -PassThru
Start-Sleep -Seconds 15
$p = Get-Process -Name "main" -ErrorAction SilentlyContinue
if (-not $p) {
    Write-Host "  FAIL 应用启动失败" -ForegroundColor Red
    exit 1
}
Write-Host "  OK 应用启动成功, PID: $($p.Id)" -ForegroundColor Green
Stop-Process -Name "main" -Force
Write-Host "  OK 应用已关闭" -ForegroundColor Green

Write-Host "`n=== 全部完成 ===" -ForegroundColor Green
Remove-Item main.spec -Force -ErrorAction SilentlyContinue