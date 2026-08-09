#!/usr/bin/env python3
"""macOS 版打包瘦身（适配自 缩包脚本/main.py 的 PythonSizeCruncher）

用法:
  python shrink_macos.py 检查 <目标文件夹> <app PID>               # 预览将移动的文件（不执行）
  python shrink_macos.py 执行 <目标文件夹> <app PID> [--keep 关键词...]  # 移动"未加载"的二进制到 <目录>_new
  python shrink_macos.py 恢复 <目标文件夹>                          # 从 _new 恢复被移动的文件
  python shrink_macos.py 清理 <目标文件夹>                          # 删除 _new 备份（确认测试通过后）

适配说明（macOS 与原脚本的差异）:
- 原脚本用 open() 检测"文件占用"，这是 Windows 文件锁机制，macOS(Unix) 无效；
  改用 lsof -p <pid> 检查运行中的 app 实际加载了哪些 .so/.dylib，未加载的视为可缩。
- 原脚本只扫 *.pyd/*.dll（Windows 二进制），macOS 改为 *.so/*.dylib。
- 白名单兜底"运行时未加载但懒加载必需"的文件（如 onnxruntime 的 dylib、
  webp 编解码、hashlib/编码类标准库等）。
"""
import subprocess
import sys
from pathlib import Path

BIN_PATTERNS = ("*.so", "*.dylib")
KEEP_FILE_TYPES = (".py", ".pyc", ".pth", ".tcl", ".json", ".zip")

# 兜底白名单：运行时未加载、但懒加载后必需的库（按代码分析确认）
KEEP_SUBSTRINGS = [
    # onnxruntime 创建推理会话时才 ctypes 加载核心 dylib
    "libonnxruntime",
    # webp 格式懒加载（应用支持 webp 检索）
    "libwebp", "libsharpyuv", "_webp",
    # Tk 运行时 / 拖拽库（已加载的 osx-arm64 由 lsof 自动保留）
    "libtk8.6", "libtcl8.6",
    # 图像编解码依赖（png/jpg/tiff/等应用支持的格式）
    "libjpeg", "libpng", "libtiff", "libopenjp2", "libfreetype", "libharfbuzz",
    "libbrotli", "libxcb", "libXau", "libz", "liblzma",
    # SSL（远程清单/模型下载）
    "libcrypto", "libssl",
    # 标准库懒加载：hashlib / 中文等编码 / 多进程
    "_md5", "_sha1", "_sha3", "_sha256", "_sha512",
    "_codecs_cn", "_codecs_jp", "_codecs_kr", "_codecs_tw", "_codecs_hk",
    "_codecs_iso2022", "_multibytecodec",
    "_multiprocessing", "_posixshmem", "resource", "mmap", "readline",
    # 其他
    "cacert.pem", "__init__", "base_library",
]


def loaded_files(pid: str) -> set[str]:
    """运行中进程实际加载的文件路径集合（lsof）。"""
    out = subprocess.run(["lsof", "-p", pid], capture_output=True, text=True).stdout
    result = set()
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 9 and parts[0] != "COMMAND":
            result.add(parts[-1])
    return result


def should_keep(path: Path, extra_keeps: list[str]) -> bool:
    s = str(path)
    if path.suffix in KEEP_FILE_TYPES:
        return True
    for kw in KEEP_SUBSTRINGS + extra_keeps:
        if kw in s:
            return True
    return False


def scan_binaries(target: Path) -> list[Path]:
    return [p for pat in BIN_PATTERNS for p in target.rglob(pat) if p.is_file()]


def do_scan(target: Path, pid: str, extra_keeps: list[str]) -> tuple[list[Path], set[str]]:
    loaded = loaded_files(pid)
    movable = []
    for f in scan_binaries(target):
        if should_keep(f, extra_keeps):
            continue
        # resolve() 兼容符号链接：Resources 下的链接会解析到 Frameworks 真身
        if str(f.resolve()) in loaded:
            continue
        movable.append(f)
    return movable, loaded


def cmd_check(target: Path, pid: str, extra_keeps: list[str]) -> None:
    movable, _ = do_scan(target, pid, extra_keeps)
    total = sum(f.stat().st_size for f in movable)
    print(f"将移动 {len(movable)} 个文件，共 {total/1e6:.2f} MB：")
    for f in movable:
        print(f"  {f.relative_to(target)} ({f.stat().st_size/1e6:.2f}MB)")


def cmd_run(target: Path, pid: str, extra_keeps: list[str]) -> None:
    movable, _ = do_scan(target, pid, extra_keeps)
    total_size = sum(f.stat().st_size for f in movable)
    backup = Path(str(target) + "_new")
    manifest = backup.parent / f"{target.name}_移动清单.txt"
    moved = []
    for f in movable:
        dest = backup / f.relative_to(target)
        dest.parent.mkdir(parents=True, exist_ok=True)
        f.rename(dest)
        moved.append(str(f))
        print(f"移动 {f.relative_to(target)}")
    manifest.write_text("\n".join(moved), encoding="utf-8")
    print(f"\n共移动 {len(moved)} 个文件（{total_size/1e6:.2f} MB）")
    print(f"备份目录: {backup}\n清单: {manifest}")
    print("下一步：重启 app 进行针对性测试；通过后执行 '清理'，失败则执行 '恢复'。")


def cmd_restore(target: Path) -> None:
    backup = Path(str(target) + "_new")
    manifest = backup.parent / f"{target.name}_移动清单.txt"
    if not manifest.exists():
        print("未找到移动清单，无法恢复")
        return
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        src = Path(line)
        dest = backup / src.relative_to(target)
        if dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            src.parent.mkdir(parents=True, exist_ok=True)
            dest.rename(src)
    print(f"已从 {backup} 恢复全部文件")


def cmd_cleanup(target: Path) -> None:
    backup = Path(str(target) + "_new")
    manifest = backup.parent / f"{target.name}_移动清单.txt"
    if backup.exists():
        import shutil
        shutil.rmtree(backup)
    if manifest.exists():
        manifest.unlink()
    print(f"已清理备份目录 {backup} 与清单 {manifest.name}")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    action = sys.argv[1]
    target = Path(sys.argv[2]).resolve()
    if not target.is_dir():
        print(f"目标文件夹不存在: {target}")
        sys.exit(1)
    extra_keeps = []
    if "--keep" in sys.argv:
        i = sys.argv.index("--keep")
        extra_keeps = sys.argv[i + 1:]

    if action == "检查":
        cmd_check(target, sys.argv[3], extra_keeps)
    elif action == "执行":
        cmd_run(target, sys.argv[3], extra_keeps)
    elif action == "恢复":
        cmd_restore(target)
    elif action == "清理":
        cmd_cleanup(target)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
