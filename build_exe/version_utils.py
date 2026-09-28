"""版本号读取 / 注入 / 校验（PRD/update_protocol_v3.md §1.4.1 的 S0 地基）。

单一真源 = `config/settings.py` 里 `WinInfo.version`，其它地方（spec 的版本资源、打包器、
构建后校验）都从这里取，不手写第二份。更新脚本运行时用 PowerShell 读同一个值
（`(Get-Item x).VersionInfo.FileVersion`），两边比的就是这个。
"""
from __future__ import annotations

from pathlib import Path
import re
import sys


SETTINGS_PY = Path(__file__).resolve().parent.parent / "config" / "settings.py"
VERSION_RE = re.compile(r'^\s*version\s*=\s*"(\d+\.\d+\.\d+)"\s*$', re.MULTILINE)


def read_version() -> str:
    """从 config/settings.py 里读出 `WinInfo.version`。"""
    m = VERSION_RE.search(SETTINGS_PY.read_text(encoding="utf-8"))
    if not m:
        raise SystemExit(f"未在 {SETTINGS_PY} 找到 WinInfo.version")
    return m.group(1)


def version_tuple(version: str) -> tuple[int, int, int, int]:
    parts = [int(x) for x in version.split(".")]
    return tuple((parts + [0, 0, 0, 0])[:4])  # type: ignore[return-value]


def make_version_info(version: str, exe_name: str = "VimgFind.exe"):
    """构造 PyInstaller 的 VSVersionInfo（给 main.spec 的 EXE(version=…) 用）。"""
    from PyInstaller.utils.win32.versioninfo import (
        FixedFileInfo, StringFileInfo, StringStruct, StringTable, VSVersionInfo,
    )

    full = f"{version}.0"
    return VSVersionInfo(
        ffi=FixedFileInfo(
            filevers=version_tuple(version),
            prodvers=version_tuple(version),
            mask=0x3F,
            flags=0x0,
            OS=0x40004,      # VOS_NT_WINDOWS32
            fileType=0x1,    # VFT_APP
            subtype=0x0,
            date=(0, 0),
        ),
        kids=[
            StringFileInfo([
                # 0409 = en-US, 04B0 = Unicode. 别用 zh-CN(0804)：.NET 的
                # FileVersionInfo（PowerShell 的 VersionInfo.FileVersion、资源管理器
                # 属性页）读不到那个语言块的字符串，实测全为空。
                StringTable("040904B0", [
                    StringStruct("CompanyName", "VimgFind"),
                    StringStruct("FileDescription", "VimgFind"),
                    StringStruct("FileVersion", full),
                    StringStruct("InternalName", exe_name),
                    StringStruct("OriginalFilename", exe_name),
                    StringStruct("ProductName", "VimgFind"),
                    StringStruct("ProductVersion", full),
                ]),
            ]),
        ],
    )


def read_exe_fileversion(path: Path) -> str:
    """读 exe 的 FileVersion 资源（`2.5.4.0` 形式）。没有资源 → 空串。

    Windows API 直读：构建侧不该依赖 PowerShell，也不该依赖 exe 能启动。
    """
    import ctypes
    from ctypes import wintypes

    class VS_FIXEDFILEINFO(ctypes.Structure):
        _fields_ = [
            ("dwSignature", wintypes.DWORD), ("dwStrucVersion", wintypes.DWORD),
            ("dwFileVersionMS", wintypes.DWORD), ("dwFileVersionLS", wintypes.DWORD),
            ("dwProductVersionMS", wintypes.DWORD), ("dwProductVersionLS", wintypes.DWORD),
            ("dwFileFlagsMask", wintypes.DWORD), ("dwFileFlags", wintypes.DWORD),
            ("dwFileOS", wintypes.DWORD), ("dwFileType", wintypes.DWORD),
            ("dwFileSubtype", wintypes.DWORD), ("dwFileDateMS", wintypes.DWORD),
            ("dwFileDateLS", wintypes.DWORD),
        ]

    version = ctypes.WinDLL("version")
    size = version.GetFileVersionInfoSizeW(str(path), None)
    if not size:
        return ""
    buf = ctypes.create_string_buffer(size)
    if not version.GetFileVersionInfoW(str(path), 0, size, buf):
        return ""
    info = ctypes.c_void_p()
    length = wintypes.UINT()
    if not version.VerQueryValueW(buf, "\\", ctypes.byref(info), ctypes.byref(length)):
        return ""
    ffi = ctypes.cast(info, ctypes.POINTER(VS_FIXEDFILEINFO)).contents
    return f"{ffi.dwFileVersionMS >> 16}.{ffi.dwFileVersionMS & 0xFFFF}.{ffi.dwFileVersionLS >> 16}.{ffi.dwFileVersionLS & 0xFFFF}"


def check_exe(path: Path, expect: str | None = None) -> str:
    """校验 exe 的 FileVersion 是否等于期望版本（默认 = WinInfo.version）。"""
    expect = expect or read_version()
    got = read_exe_fileversion(path)
    if got != f"{expect}.0":
        raise SystemExit(f"FileVersion 不符：{path}\n  期望 {expect}.0，实际 {got or '(无版本资源)'}")
    return got


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "--check":
        print(f"FileVersion OK: {check_exe(Path(sys.argv[2]))}")
    else:
        print(read_version())
