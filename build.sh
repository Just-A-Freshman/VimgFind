#!/bin/bash
# =============================================================================
# VimgFind macOS 一键构建脚本
#
# 流程: 前置检查 → pyinstaller(-D + bundleID) → 启动(供缩包判断) →
#       4 文件夹缩包 → 终止 → 最后签名 → 验证
#
# 注意顺序: 缩包在签名之前（缩包会移走文件使签名失效），签名必须是最后一步。
# 产物: dist/VimgFind.app （ad-hoc 签名，本机/自测用；正式分发需 Developer ID）
#
# 用法: ./build.sh          # 使用 .venv-build 构建环境
#       BUILD_ENV=xxx ./build.sh   # 指定其他构建环境
# =============================================================================
set -e
cd "$(dirname "$0")"

BUILD_ENV="${BUILD_ENV:-.venv-build}"
BUILD_PY="$BUILD_ENV/bin/python"
APP="dist/VimgFind.app"
APP_PROC="VimgFind.app/Contents/MacOS/VimgFind"
FRW="$HOME/Library/Frameworks/Python.framework/Versions/3.12"
export TCL_LIBRARY="$FRW/lib/tcl8.6"
export TK_LIBRARY="$FRW/lib/tk8.6"

echo "== 构建环境: $BUILD_ENV =="
[ -x "$BUILD_PY" ] || { echo "!! 构建环境不存在: $BUILD_ENV（请先按 README 3.5 搭建）"; exit 1; }

# ── 0. 前置检查: 默认数据模板 ─────────────────────────────
echo "== 0/6 前置检查 =="
[ -f "config/data/models/osnet/model.onnx" ] || {
  echo "!! 缺少默认模型 config/data/models/osnet/model.onnx"
  echo "   （models/ 被 .gitignore 忽略，需自行放入，可从 models.json 的 download_url 下载）"
  exit 1
}
grep -q "未命名" config/data/setting.json && {
  echo "!! config/data/setting.json 含开发期自定义菜单，请先清理"
  exit 1
}
echo "  ✓ 默认数据就绪"

# ── 1. 打包 ────────────────────────────────────────────────
echo "== 1/6 pyinstaller 打包 (-D onedir) =="
"$BUILD_PY" -m PyInstaller -y -D -w --name VimgFind \
  --icon config/data/favicon.icns \
  --osx-bundle-identifier com.vimgfind.app \
  --add-data "config/data:config/data" \
  --collect-all tkinterdnd2 --collect-all ttkbootstrap \
  main.py

# ── 2. 启动（缩包需要运行中的 app，lsof 判断"未加载"文件）──
echo "== 2/6 启动 app（供缩包判断） =="
pkill -f "$APP_PROC" 2>/dev/null || true
sleep 1
open "$APP"
sleep 22   # 等待模型/索引等后台初始化完成，加载全部必需库
PID=$(pgrep -f "$APP_PROC" | head -1)
[ -n "$PID" ] || { echo "!! app 未能启动，缩包无法进行"; exit 1; }
echo "  app PID=$PID"

# ── 3. 缩包（4 个文件夹，逐个清理备份）────────────────────
echo "== 3/6 缩包 =="
SHRINK="缩包脚本/shrink_macos.py"
for folder in \
  "dist/VimgFind.app/Contents/Resources/tkinterdnd2/tkdnd" \
  "dist/VimgFind.app/Contents/Frameworks/tkinterdnd2/tkdnd/osx-x64" \
  "dist/VimgFind.app/Contents/Frameworks/PIL" \
  "dist/VimgFind.app/Contents/Frameworks/numpy" \
  "dist/VimgFind.app/Contents/Frameworks/python3__dot__12/lib-dynload"; do
  "$BUILD_PY" "$SHRINK" 执行 "$folder" "$PID" > /dev/null
  "$BUILD_PY" "$SHRINK" 清理 "$folder" > /dev/null
done
# 清理移走文件留下的断链符号链接
find "$APP" -type l ! -exec test -e {} \; -delete 2>/dev/null || true
echo "  ✓ 缩包完成"

# ── 4. 终止 app ───────────────────────────────────────────
echo "== 4/6 终止 app =="
pkill -f "$APP_PROC" 2>/dev/null || true
sleep 1

# ── 5. 签名（缩包后必须最后做）────────────────────────────
echo "== 5/6 ad-hoc 签名 =="
codesign --force --deep --sign - "$APP"

# ── 6. 验证 ───────────────────────────────────────────────
echo "== 6/6 验证 =="
codesign --verify "$APP" && echo "  ✓ 签名验证通过"
codesign -dv "$APP" 2>&1 | grep -E "Identifier|Signature" | sed 's/^/  /'
du -sh "$APP" | sed 's/^/  体积: /'
echo ""
echo "完成: $APP"
echo "提示: 本机可直接运行；分发给他人见 README 3.6 分发说明。"
