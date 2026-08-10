# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        # numpy 2.x 的 C 扩展 _multiarray_umath.pyd 在初始化时通过 C API 导入此模块，
        # PyInstaller 的 modulegraph 看不到 C 层导入，必须手动声明，否则运行时崩（ImportError）。
        'numpy._core._exceptions',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # --- numpy 未使用的子模块（运行时实测从不加载，省 ~0.83MB 二进制 + ~0.58MB PYZ） ---
        'numpy.random',
        'numpy.fft',
        'numpy.testing',
        'numpy.f2py',
        'numpy.ma',
        'numpy.polynomial',
        'numpy.char',
        'numpy.rec',
        'numpy.strings',
        'numpy.matlib',
        'numpy.ctypeslib',
        # numpy.typing 仅在 typing.TYPE_CHECKING 分支中被引用（onnxruntime 的
        # onnxruntime_inference_collection.py），运行时从不加载，纯类型标注，可安全排除。
        'numpy.typing',
        # --- onnxruntime 未使用的子模块 ---
        # onnxruntime.transformers.machine_info 只在 print_debug_info() 里惰性导入（还需 psutil+py3nvml），
        # 应用从不调用该函数。
        'onnxruntime.transformers',
        'onnxruntime.capi.onnxruntime_collect_build_info',
        # --- Pillow：排除不支持的格式插件 + 未使用的高级功能模块 ---
        # 依据：config/settings.py 的 ext_group_map 只支持 PNG/JPG/WebP/GIF/BMP/TIFF/PSD；
        # PIL.Image.init() 对每个插件 try/except ImportError，排除后自动跳过，不报错。
        # 安全保留（代码/依赖链实测需要）：Image, ImageFile, ImageDraw, ImageFont, ImageTk, ImageOps,
        #   ImageColor, ImageMode, ImagePalette, ImagePath, ImageSequence, ExifTags, JpegPresets,
        #   TiffTags, PaletteFile, Jpeg, features, _binary, _util, _deprecate, _typing, _version,
        #   ImageChops/ImageMath（GifImagePlugin/ImageOps 依赖）, ImageText（ImageDraw 依赖），
        #   ImageGrab（ttkbootstrap colordropper 依赖）, GimpGradientFile/GimpPaletteFile（ImagePalette 依赖），
        #   以及 7 个格式插件：Bmp/Gif/Jpeg/Png/Psd/Tiff/WebP
        # 排除 AvifImagePlugin 同时去掉 _avif.pyd（1.8MB 二进制）；ImageCms 去掉 _imagingcms.pyd。
        # --- 未支持的格式插件 ---
        'PIL.AvifImagePlugin',
        'PIL.BlpImagePlugin',
        'PIL.BufrStubImagePlugin',
        'PIL.CurImagePlugin',
        'PIL.DcxImagePlugin',
        'PIL.DdsImagePlugin',
        'PIL.EpsImagePlugin',
        'PIL.FitsImagePlugin',
        'PIL.FliImagePlugin',
        'PIL.FpxImagePlugin',
        'PIL.FtexImagePlugin',
        'PIL.GbrImagePlugin',
        'PIL.GribStubImagePlugin',
        'PIL.Hdf5StubImagePlugin',
        'PIL.IcnsImagePlugin',
        'PIL.IcoImagePlugin',
        'PIL.ImImagePlugin',
        'PIL.ImtImagePlugin',
        'PIL.IptcImagePlugin',
        'PIL.Jpeg2KImagePlugin',
        'PIL.McIdasImagePlugin',
        'PIL.MicImagePlugin',
        'PIL.MpegImagePlugin',
        'PIL.MpoImagePlugin',
        'PIL.MspImagePlugin',
        'PIL.PalmImagePlugin',
        'PIL.PcdImagePlugin',
        'PIL.PcxImagePlugin',
        'PIL.PdfImagePlugin',
        'PIL.PdfParser',
        'PIL.PixarImagePlugin',
        'PIL.PpmImagePlugin',
        'PIL.QoiImagePlugin',
        'PIL.SgiImagePlugin',
        'PIL.SpiderImagePlugin',
        'PIL.SunImagePlugin',
        'PIL.TgaImagePlugin',
        'PIL.WmfImagePlugin',
        'PIL.XVThumbImagePlugin',
        'PIL.XbmImagePlugin',
        'PIL.XpmImagePlugin',
        # --- 未使用的高级功能模块 ---
        'PIL.ImageCms',
        'PIL.ImageShow',
        'PIL.ImageWin',
        'PIL.ImageFilter',
        'PIL.ImageEnhance',
        'PIL.ImageMorph',
        'PIL.ImageStat',
        # --- pywin32 附带的 MFC IDE（Pythonwin，省 ~5.7MB）---
        # win32com.client.makepy 是断链关键：makepy -> pywin -> win32ui
        'win32com.client.makepy',
        'pythonwin',
        'pywin',
        'win32ui',
    ],
    noarchive=False,
)

# --- onnxruntime：过滤不需要的 DLL（省 ~15MB）---
# pyinstaller-hooks-contrib 的 hook-onnxruntime.py 用 collect_dynamic_libs('onnxruntime')
# 把 capi 目录下所有 DLL 都收进来。实测：onnxruntime_pybind11_state.pyd 的 PE 导入表
# 不依赖 onnxruntime.dll（PyInstaller 的 bindepend 亦确认），且去掉这两个 DLL 后
# CPUExecutionProvider 推理（用项目真实模型 image_model.onnx）完全正常。
# onnxruntime.dll 是共享运行时（Azure/训练等 provider 用），providers_shared.dll 是
# AzureExecutionProvider 的 bridge，应用只用 CPUExecutionProvider，均不需要。
_ORT_UNNEEDED = {
    'onnxruntime\\capi\\onnxruntime.dll',
    'onnxruntime\\capi\\onnxruntime_providers_shared.dll',
}
a.binaries = [b for b in a.binaries if b[0] not in _ORT_UNNEEDED]
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='main',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['config\\data\\favicon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='main',
)
