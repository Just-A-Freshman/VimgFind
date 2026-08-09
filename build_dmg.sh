#!/bin/bash
# 构建 VimgFind 分发 DMG（含 install.sh + VimgFind.app）
set -e
cd "$(dirname "$0")"

APP="dist/VimgFind.app"
STAGE="release/_staging"
DMG="dist/VimgFind-install.dmg"

[ -d "$APP" ] || { echo "错误：缺少 $APP，请先打包（见 build.sh）"; exit 1; }

rm -rf "$STAGE"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
cp release/install.command "$STAGE/"
cp release/使用说明.txt "$STAGE/"

hdiutil create -volname "VimgFind" -srcfolder "$STAGE" -ov -quiet "$DMG"
rm -rf "$STAGE"

echo "✓ 已生成 $DMG（$(du -sh "$DMG" | cut -f1)）"
echo "  分发时用户: 下载 → 双击挂载 → 运行 DMG 内的 install.command"
