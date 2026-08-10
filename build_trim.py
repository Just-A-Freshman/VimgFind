# -*- coding: utf-8 -*-
"""
构建后裁剪脚本：在 PyInstaller 构建完成后运行，进一步瘦身 dist。

用法（在项目根目录，先 conda activate vimgfind）：
    pyinstaller main.spec --noconfirm --clean
    python build_trim.py [dist路径，默认 dist/main]

裁剪项（均已在本机实测验证，应用可正常启动 + 加载模型推理）：
  - tcl/encoding  只保留 cp936.enc（Tk 中文显示需要 GBK；其余 81 个编码文件 -1.6MB）
  - tcl/msgs、tk/msgs  全部删除（Tcl/Tk 本地化消息，应用为中文 UI，-458KB）
  - tk/images     只留 README（Tk 内置 logo，-120KB）
  - tcl8          只留 8.5/msgcat（-236KB）
  - tcl/tzdata    整个删除（Tcl clock 时区数据；tkinter/ttkbootstrap 不用，-2.0MB；
                  如担心可加 --keep-tzdata 保留）
  - api-ms-win-crt-*.dll 删除（Win10+ 系统自带这些 UCRT API set，-412KB；
                  仅 Win10 1809+ 目标环境可删，Win7/8 需保留）

注意：
  构建时必须先 `conda activate vimgfind`（或保证 PATH 里 vimgfind 的 Library/bin 优先）。
  否则 PyInstaller 的 _tkinter hook 会从 base 环境解析到旧版 tcl86t.dll，
  与 vimgfind 的 init.tcl 版本不匹配，运行时直接崩（Tcl version conflict）。
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path


def trim(dist: Path, keep_tzdata: bool) -> None:
    internal = dist / "_internal"
    if not internal.exists():
        sys.exit(f"找不到 {internal}，请确认 dist 路径")

    # 1) tcl/encoding 只留 cp936.enc
    enc = internal / "tcl" / "encoding"
    if enc.exists():
        cp936 = enc / "cp936.enc"
        for f in enc.iterdir():
            if f.name != "cp936.enc":
                f.unlink()
        if not cp936.exists():
            sys.exit("tcl/encoding/cp936.enc 不存在，请确认 Tcl 版本含 GBK 编码")

    # 2) tcl/msgs、tk/msgs
    for msgs in (internal / "tcl" / "msgs", internal / "tk" / "msgs"):
        if msgs.exists():
            shutil.rmtree(msgs)

    # 3) tk/images 只留 README
    imgs = internal / "tk" / "images"
    if imgs.exists():
        readme = imgs / "README"
        for f in imgs.iterdir():
            if f.name != "README":
                f.unlink()

    # 4) tcl8 只留 8.5/msgcat-*.tm
    tcl8 = internal / "tcl8"
    if tcl8.exists():
        for sub in tcl8.iterdir():
            if sub.name == "8.5":
                for f in sub.iterdir():
                    if not f.name.startswith("msgcat-"):
                        f.unlink()
            else:
                shutil.rmtree(sub)

    # 5) tzdata
    if not keep_tzdata:
        tzdata = internal / "tcl" / "tzdata"
        if tzdata.exists():
            shutil.rmtree(tzdata)

    # 6) api-ms-win-crt-*.dll
    removed_crt = 0
    for dll in internal.glob("api-ms-win-crt-*.dll"):
        dll.unlink()
        removed_crt += 1

    print(f"裁剪完成: {dist}")
    print(f"  tcl: {enc.parent} 只留 cp936.enc")
    print(f"  tzdata: {'保留' if keep_tzdata else '已删除'}")
    print(f"  api-ms-win-crt-*.dll: 删除 {removed_crt} 个")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("dist", nargs="?", default="dist/main", help="dist 目录，默认 dist/main")
    ap.add_argument("--keep-tzdata", action="store_true", help="保留 tcl/tzdata")
    args = ap.parse_args()
    trim(Path(args.dist), keep_tzdata=args.keep_tzdata)
