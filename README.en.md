# VimgFind

<div align="center">

**Local AI Image Search · Search by Image · Search by Text**

Platforms: Windows · macOS

[中文](./README.md) · [Changelog](https://github.com/Just-A-Freshman/VimgFind/releases/tag/program2.5)

</div>

## 1. Introduction

VimgFind is a **fully local** AI image search tool. It supports both search-by-image and search-by-text (depending on the model you select).

Tech stack:

- Vector index: **HNSW** — prioritizes precision over raw speed, balancing search quality and memory usage
- Model inference: **ONNX Runtime** — efficient local inference, models ready to use after one download
- UI: **Python tkinter + ttkbootstrap** — clean, separated Search / Index / Model tabs

Screenshot:
![VimgFind main UI](https://raw.githubusercontent.com/Just-A-Freshman/image-bed/main/Typora/image-20260713201627284.png)

## 2. Features

- **Three ways to input an image**: browse a file, paste the clipboard with `Ctrl/⌘ + V`, or drag & drop images onto the window;
- **Search filters**: similarity threshold, file type, file size, folder, exact-duplicate removal, and other basic filters;
- **Multi-image search**: drag or paste several images at once — the first one searches immediately, the rest are searched lazily as you page through results, without blocking;
- **Swappable models**: 5 pre-converted models covering semantic, detail, robustness, Chinese-semantic, and other retrieval orientations;
- **Exclusion rules**: keep images you never want to see (memes, cache thumbnails, etc.) out of the index at indexing time;
- **Customizable context menu**: toggle built-in items, assign shortcuts, drag to reorder, and write custom commands with template variables;
- **Auto index update** (still room for improvement): after the program starts, it incrementally updates the index when the system is idle (default 300 s), without interrupting your work.

## 3. Quick Start

### 3.1 Installation

**macOS (recommended)**

Open Terminal and paste the following command (it downloads and launches the app automatically):

```sh
/bin/bash -c "$(curl -fsSL https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-macos-install.sh)"
```

> Do not manually download the dmg from Releases: macOS' default download flow applies quarantine to unsigned apps and blocks them from opening. Downloading via `curl` bypasses that restriction.

**Windows**

- Full package: [VimgFind-v2.5.2 (GitHub)](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-win64.zip)
- Update package: [v2.5.2 update (GitHub)](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-win64-update.zip)

### 3.2 First Run (three steps to searching)

1. **Add an index folder**: open the **Index** tab → add the folder(s) you want to search;
2. **Update index**: click *Update Index* — the program scans folders and encodes images into vectors (a few minutes for tens of thousands of images; multi-threaded, runs in the background);
3. **Search**: switch to the **Search** tab, browse/paste/drag an image, or type text and press Enter.

> Since 2.5.1, the packaged program only bundles the lightest OSNet model for easier distribution. Other models can be viewed and downloaded in the **Model** tab.

### 3.3 Switching the UI Language

The app ships with both **中文 (Chinese)** and **English** UI languages. Open *General Settings* → *General* tab, then pick your language from the *Display Language* dropdown; a restart is needed for the change to fully take effect.

## 4. Resource Usage & Performance Tips

- **Disk**: index files are roughly 1 MB per 400 images — usually negligible;
- **Memory**: models take ~170 MB (OSNet) up to ~1.6 GB (Chinese-CLIP); the HNSW index is fully loaded into memory, ~6–8 GB per million images;
- **Tips**: for large libraries, use different models for different folders to spread index memory, and use exclusion rules to filter memes/thumbnails at the source — reducing both memory pressure and retrieval noise.

## 5. Build from Source

### Windows

Requirements: Python 3.9+ (conda recommended):

```powershell
git clone https://github.com/Just-A-Freshman/VimgFind.git
cd VimgFind
conda create -n vimgfind python=3.12 && conda activate vimgfind
pip install -r requirements.txt
python ./main.py
```

Package manually:

```powershell
pip install pyinstaller==6.2
pyinstaller -D main.py -i config/data/favicon.ico -w
```

After packaging, copy `config/data/` and `docs/` into `_internal`.

### macOS

See the instructions in the `version2.5-macos` branch.

## 6. Updates & Feedback

- Changelog: [VimgFind v2.5.2](https://github.com/Just-A-Freshman/VimgFind/releases/tag/program2.5)
- Releases: [All versions](https://github.com/Just-A-Freshman/VimgFind/releases)
- Bugs & feature requests: [Open an Issue](https://github.com/Just-A-Freshman/VimgFind/issues)

## 7. Roadmap

- [x] Multi-model & multi-index: isolated indexes per model, switch freely
- [x] macOS support

> A detailed help manual ships with the app (Settings → Help), covering index capacity, exclusion-rule syntax, custom commands, and more.
