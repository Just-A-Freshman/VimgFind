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

# 自编译的 Tk 8.6.15（修 TTK_STATE_OPEN/user1 映射，见 patch/README.md）：
# 必须盖过 PyInstaller 从环境里拿来的上游版本，否则 Treeview 自定义样式失效
Write-Host "`n=== 步骤3.5: 替换 tk86t.dll ===" -ForegroundColor Cyan
if (-not (Test-Path "patch/tk86t.dll")) { throw "缺少 patch/tk86t.dll" }
Copy-Item -Force "patch/tk86t.dll" "dist/main/_internal/tk86t.dll"
$a = (Get-FileHash 'patch/tk86t.dll' -Algorithm MD5).Hash
$b = (Get-FileHash 'dist/main/_internal/tk86t.dll' -Algorithm MD5).Hash
if ($a -ne $b) { throw "tk86t.dll 替换后哈希不一致" }
Write-Host ("  OK tk86t.dll = patch 版 " + $a.Substring(0, 12))

Write-Host "`n=== 步骤4: 验证构建产物 ===" -ForegroundColor Cyan
if (-not (Test-Path "dist/main/main.exe")) { throw "main.exe 未生成" }
Write-Host "  OK main.exe 已生成"
# tk86t.dll 必须是 patch 里那份（别被上游版本盖回去）
if ((Get-FileHash 'dist/main/_internal/tk86t.dll' -Algorithm MD5).Hash -ne (Get-FileHash 'patch/tk86t.dll' -Algorithm MD5).Hash) {
    throw "dist 里的 tk86t.dll 不是 patch 版本"
}
# FileVersion 必须 == WinInfo.version（更新脚本靠它判版本 / 做包自检）
python build_exe/version_utils.py --check dist/main/main.exe
if ($LASTEXITCODE -ne 0) { throw "FileVersion 校验失败" }
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