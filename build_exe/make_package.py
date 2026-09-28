"""生成 VimgFind 全量更新包（目录式 + zip）—— PRD/update_protocol_v3.md §1、update_plan_v3.md S0。

产物结构（目录形态才是本体，zip 只是运输形式）：

    VimgFind-<ver>-<tag>-update/
      _update/
        update.bat              <- 唯一必须项、唯一入口
        VimgFind<ver>.exe       <- 新主程序（更新器负责改名成目标现有 exe 名）
      _internal/...             <- 安装目录镜像（用户数据白名单除外）
      更新请点我.hta              <- 手动更新入口（可选，但发布包里应该带着）

用户数据（setting.json / models/ / error.log / temp/）绝不进包：它们要么属于用户，
要么是运行期产物；打进去就会覆盖别人的数据。

`--update-dir` 的**父目录**里除 `_update/` 之外的东西会原样搬到包根
（如 `build_exe/update_pkg/更新请点我.hta` → 包根同名文件）。

用法：
    python build_exe/make_package.py                     # 用 dist/main + WinInfo.version
    python build_exe/make_package.py --dist dist/main --out dist/VimgFind-2.5.4-win64-update.zip
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import shutil
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
from version_utils import check_exe, read_version  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
PKG_NAME_RE = r"^VimgFind-\d+\.\d+\.\d+-(win64|macos|linux-x64)-update$"

# 相对 _internal 的路径：属于用户 / 运行期，绝不进包
KEEP_OUT_DIRS = ("config/data/models", "temp")
KEEP_OUT_FILES = ("config/data/setting.json", "config/data/error.log")


def platform_tag() -> str:
    return {"win32": "win64", "darwin": "macos"}.get(sys.platform, "linux-x64")


def find_exe(dist: Path) -> Path:
    for pattern in ("main.exe", "VimgFind*.exe"):
        for p in sorted(dist.glob(pattern)):
            if p.is_file():
                return p
    raise SystemExit(f"{dist} 里找不到主程序（main.exe / VimgFind*.exe）")


def copy_internal(src: Path, dst: Path) -> None:
    """把 dist/_internal 镜像进包，跳过用户数据白名单。"""
    keep_dirs = {p.replace("\\", "/") for p in KEEP_OUT_DIRS}
    keep_files = {p.replace("\\", "/") for p in KEEP_OUT_FILES}
    for item in src.rglob("*"):
        rel = item.relative_to(src).as_posix()
        if any(rel == d or rel.startswith(d + "/") for d in keep_dirs):
            continue
        if rel in keep_files:
            continue
        target = dst / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def pyz_modules(exe: Path) -> set[str]:
    """exe 内 PYZ 里打包了哪些模块（用来做"依赖没丢"的发布前预检）。"""
    from PyInstaller.archive.readers import CArchiveReader

    reader = CArchiveReader(str(exe))
    for name in reader.toc:
        if name.endswith(".pyz"):
            return set(reader.open_embedded_archive(name).toc)
    return set()


# 发布前必须存在于 exe 里的模块：
#   utils.single_instance  —— 端口 50781 的持有者，更新脚本靠它判"应用还在跑"（契约 §3.1）
#   pystray.* / PIL / six  —— 2.5.4 新增的托盘依赖链（纯 python，住在 exe 的 PYZ 里，
#                             不 需要也不应该再往 _internal/ 拷一份）
REQUIRED_MODULES = (
    "utils.single_instance",
    "controllers.tray_controller",
    "views.tray",
    "pystray",
    "pystray._win32",
    "pystray._util.win32",
    "PIL.Image",
    "PIL.IcoImagePlugin",   # pystray 把图标 PNG 存成 ICO 才能拿到 HICON（少它=托盘静默消失）
    "six",
)


def args_patch_dir() -> Path | None:
    """verify() 里要用到 --patch-dir（不额外传参，保持调用点干净）。"""
    return _PATCH_DIR[0]


_PATCH_DIR: list[Path | None] = [None]


def verify(pkg: Path, version: str) -> None:
    """契约 §1 的不变量。任何一条不满足都说明这个包不能发。"""
    if not (pkg / "_update" / "update.bat").is_file():
        raise SystemExit("包含不变量失败：缺 _update/update.bat")
    bats = [p for p in pkg.rglob("update.bat")]
    if len(bats) != 1:
        raise SystemExit(f"包含不变量失败：包里 update.bat 应恰好 1 个，实际 {len(bats)}：{bats}")
    if not (pkg / f"_update/VimgFind{version}.exe").is_file():
        raise SystemExit(f"包含不变量失败：缺 _update/VimgFind{version}.exe")
    internal = pkg / "_internal"
    for rel in (*KEEP_OUT_DIRS, *KEEP_OUT_FILES):
        if (internal / rel).exists():
            raise SystemExit(f"包含不变量失败：用户数据漏进包了 → _internal/{rel}")
    # 帮助文档 + 翻译必须随包走：更新时它们要整树覆盖目标里的旧版（镜像是 /MIR）
    for rel in ("base_library.zip", "config/data/locales/en-US.json", "config/data/locales/zh-CN.json",
                "config/data/locales/_languages.json", "config/data/docs/help_zh-CN.html",
                "config/data/favicon.png"):
        if not (internal / rel).exists():
            raise SystemExit(f"包含不变量失败：缺 _internal/{rel}")
    if not list((internal / "config/data/docs/image").glob("*.png")):
        raise SystemExit("包含不变量失败：帮助文档的配图没进包（_internal/config/data/docs/image 为空）")
    if not list(internal.glob("python3*.dll")):
        raise SystemExit("包含不变量失败：缺 _internal/python3*.dll（不是 2.5.1+ 新布局）")
    # 热修文件：patch/ 是唯一来源 → 包里两处都必须等于它（防止"打了补丁没重建"）
    patch_src = (args_patch_dir() or Path())
    if patch_src.is_dir():
        for item in sorted(patch_src.iterdir()):
            if item.is_dir() or item.suffix.lower() == ".md":
                continue
            want = hashlib.md5(item.read_bytes()).hexdigest()
            for where in ("_update/_internal", "_internal"):
                got_path = pkg / where / item.name
                if not got_path.is_file():
                    raise SystemExit(f"包含不变量失败：{where}/{item.name} 不在包里（patch/ 里有）")
                got = hashlib.md5(got_path.read_bytes()).hexdigest()
                if got != want:
                    raise SystemExit(f"包含不变量失败：{where}/{item.name} 与 patch/{item.name} 不一致"
                                     f"（{got[:12]} != {want[:12]}）→ 该跑一次 build_local 重建 dist")

    # 手动更新入口（hta）在包根，名字与老包一致
    hta = [p for p in pkg.glob("*.hta")]
    if not hta:
        raise SystemExit("包含不变量失败：包根没有 .hta 手动更新入口")
    payload_exe = pkg / f"_update/VimgFind{version}.exe"
    check_exe(payload_exe, version)
    missing = [m for m in REQUIRED_MODULES if m not in pyz_modules(payload_exe)]
    if missing:
        raise SystemExit(f"包含不变量失败：exe 的 PYZ 里缺模块 {missing}")


def zip_package(pkg: Path, out: Path) -> str:
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for item in sorted(pkg.rglob("*")):
            if item.is_file():
                zf.write(item, f"{pkg.name}/{item.relative_to(pkg).as_posix()}")
    return hashlib.sha256(out.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description="生成 VimgFind 全量更新包")
    ap.add_argument("--dist", type=Path, default=ROOT / "dist" / "main", help="安装目录（含 main.exe 与 _internal）")
    ap.add_argument("--version", default=None, help="默认取 config/settings.py 的 WinInfo.version")
    ap.add_argument("--tag", default=None, help="默认按平台：win64 / macos / linux-x64")
    ap.add_argument("--update-dir", type=Path, default=ROOT / "build_exe" / "update_pkg" / "_update",
                    help="_update/ 的来源目录（必须含 update.bat）")
    ap.add_argument("--out", type=Path, default=None, help="zip 输出路径（默认 <out-dir>/<包名>.zip）")
    ap.add_argument("--patch-dir", type=Path, default=ROOT / "patch",
                    help="热修文件目录（默认仓库 patch/）：里面的文件会被放到包的 _update\_internal\ 下，"
                         "由更新脚本的补丁区按相对路径覆盖到目标 _internal（例：patch\tk86t.dll → "
                         "_update\_internal\tk86t.dll → 目标 _internal\tk86t.dll）")
    ap.add_argument("--extra-dir", type=Path, default=None,
                    help="包根额外文件（.hta 等）的来源目录；默认 = --update-dir 的父目录")
    ap.add_argument("--out-dir", type=Path, default=None,
                    help="包目录与 zip 的父目录（默认 dist 的父目录=dist/）；测试夹具用它把产物挪出 dist")
    args = ap.parse_args()

    version = args.version or read_version()
    tag = args.tag or platform_tag()
    dist: Path = args.dist.resolve()
    update_dir: Path = args.update_dir.resolve()
    out_dir: Path = (args.out_dir or dist.parent).resolve()
    if not (update_dir / "update.bat").is_file():
        raise SystemExit(f"缺少入口脚本：{update_dir / 'update.bat'}")

    pkg = out_dir / f"VimgFind-{version}-{tag}-update"
    out_dir.mkdir(parents=True, exist_ok=True)
    if not __import__("re").fullmatch(PKG_NAME_RE, pkg.name):
        raise SystemExit(f"包根命名不合契约：{pkg.name}")

    print(f"包根: {pkg}")
    if pkg.exists():
        shutil.rmtree(pkg)
    pkg.mkdir(parents=True)

    exe = find_exe(dist)
    check_exe(exe, version)                      # 构建产物自带 FileVersion 校验
    (pkg / "_update").mkdir()
    shutil.copy2(exe, pkg / "_update" / f"VimgFind{version}.exe")
    # _update/ 是“补丁区 + 入口”：整个目录树都搬过去，嵌套路径（如
    # _update/_internal/config/data/...）按相对安装根的路径子生效（契约 §1.2）。
    # （旧实现只拷顶层文件，静默丢了补丁子目录——测试夹具的挖出来的。）
    for item in update_dir.iterdir():
        if item.is_dir():
            shutil.copytree(item, pkg / "_update" / item.name, dirs_exist_ok=True)
        else:
            shutil.copy2(item, pkg / "_update" / item.name)
    # 热修文件（patch/ → _update/_internal/）：走"补丁区"，比 _internal 镜像更硬——
    # 将来出瘦身包（不含 _internal）时它照样落地（契约 §1.2）。README/md 不打包。
    patch_dir: Path = args.patch_dir.resolve() if args.patch_dir else None
    if patch_dir and patch_dir.is_dir():
        target_dir = pkg / "_update" / "_internal"
        target_dir.mkdir(parents=True, exist_ok=True)
        for item in sorted(patch_dir.iterdir()):
            if item.is_dir():
                shutil.copytree(item, target_dir / item.name, dirs_exist_ok=True)
            elif item.suffix.lower() != ".md":
                shutil.copy2(item, target_dir / item.name)

    # 包根的额外文件（如手动更新入口 更新请点我.hta）：
    # update_dir 的父目录里，除 _update/ 之外的东西原样搬到包根
    extra_dir: Path = args.extra_dir.resolve() if args.extra_dir else update_dir.parent
    if extra_dir.is_dir():
        for item in extra_dir.iterdir():
            if item.name == update_dir.name:
                continue
            # 别把产物目录（包目录 / zip 目录）再拷回包里：--out-dir 落在 extra-dir
            # 里面时会无限递归（验收夹具就踩过一次）
            resolved = item.resolve()
            if any(t == resolved or t.is_relative_to(resolved)
                   for t in (pkg.resolve(), out_dir.resolve())):
                continue
            if item.is_dir():
                shutil.copytree(item, pkg / item.name, dirs_exist_ok=True)
            else:
                shutil.copy2(item, pkg / item.name)
    copy_internal(dist / "_internal", pkg / "_internal")
    _PATCH_DIR[0] = patch_dir
    verify(pkg, version)

    out = args.out or out_dir / f"{pkg.name}.zip"
    digest = zip_package(pkg, out)
    size = out.stat().st_size
    files = sum(1 for p in pkg.rglob("*") if p.is_file())
    print(f"zip : {out}")
    print(f"大小: {size / 1024 / 1024:.1f} MB / {files} 个文件")
    print(f"sha256: {digest}")
    print(f"载荷 exe: {pkg / '_update' / f'VimgFind{version}.exe'}（FileVersion {version}.0 OK）")


if __name__ == "__main__":
    main()
