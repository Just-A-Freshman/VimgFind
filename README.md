# VimgFind

<div align="center">

**本地 AI 搜图工具 · 以图搜图 · 以文搜图**

支持平台：Windows · macOS

[English](./README.en.md) · [更新日志](https://github.com/Just-A-Freshman/VimgFind/releases/tag/program2.5)

</div>

## 1. 项目简介

VimgFind 是一款运行在**本地**的 AI 搜图工具。同时支持以图搜图和以文搜图（取决于选择的模型）的功能。

核心技术栈：

- 向量索引：**HNSW** 算法，以精度换速度，平衡搜索质量与内存占用
- 模型推理：**ONNX Runtime**，本地高效推理，模型即下即用
- 界面开发：**Python tkinter + ttkbootstrap**，搜索 / 索引 / 模型分页管理

界面展示：
![VimgFind 主界面](https://raw.githubusercontent.com/Just-A-Freshman/image-bed/main/Typora/image-20260713201627284.png)

## 2. 功能特性

- **三种方式输入图片**：点击浏览选择文件、`Ctrl/⌘ + V` 粘贴剪贴板图片、直接拖拽图片到窗口；
- **搜索过滤**：相似度阈值、文件类型、文件大小、所属文件夹、完全去重等基础过滤功能；
- **多图搜索**：一次拖入/粘贴多张图片，第一张立即出结果，翻页时按需搜索后续图片，互不阻塞；
- **多种模型可切换**：内置 5 个预转换模型，覆盖语义、细节、抗干扰、中文语义等不同检索取向；
- **索引排除规则**：在索引阶段就把“永远不想搜到”的图片（表情包、缓存缩略图等）挡在门外；
- **自定义右键菜单**：控制内置菜单项显示与快捷键，支持拖拽排序，还可编写带变量的自定义命令；
- **自动更新索引**（尚有提升空间）：程序启动后会系统空闲时（默认 300 秒）自动增量更新索引，不打扰工作。



## 3. 快速上手

### 3.1 安装

**macOS 用户（推荐）**

打开终端，粘贴以下命令（脚本会自动下载并启动应用）：

```sh
/bin/bash -c "$(curl -fsSL https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-macos-install.sh)"
```

> 请不要手动从 Release 下载 dmg 文件：macOS 默认下载方式会对未签名 App 强制隔离（quarantine），导致无法打开；用 `curl` 这类下载工具可绕过该限制。

**Windows 用户**

- 完整程序：[Github 下载 VimgFind-v2.5.2](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-win64.zip) ｜ [蓝奏云下载](https://wwbbm.lanzouv.com/iKpAQ40w561e)
- 更新程序：[Github 下载 v2.5.2 更新包](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-win64-update.zip) ｜ [蓝奏云下载](https://wwbbm.lanzouv.com/ikIpA40w58di)



### 3.2 第一次使用（三步开始搜索）

1. **添加索引目录**：进入“索引”选项卡 → 添加你想搜索的图片文件夹；
2. **更新索引**：点击“更新索引”，程序会扫描目录并将图片编码为向量（首次数万张约需几分钟，多线程并行，可在后台进行）；
3. **开始搜索**：切到“搜索”选项卡，浏览/粘贴/拖拽一张图片，或直接输入文字按回车。

> 从2.5.1开始，打包后的程序仅内置最轻的Osnet模型，以便于分发。其他模型文件请切换到“模型”选项卡查看与下载。

### 3.3 切换界面语言

程序内置**中文**与**English**两种界面语言。打开“通用设置”→ 选择“常规”选项卡，在“显示语言”下拉框中选择即可切换；切换后提示重启应用以完全生效。



## 4. 资源占用与性能建议

- **磁盘**：索引文件约 400 张图片 / 1 MB，通常可忽略；
- **内存**：模型约占 170 MB（OSNet）～ 1.6 GB（Chinese-CLIP）；HNSW 索引需整体加载进内存， 100 万张图占用约 6–8 GB；
- **建议**：图片量大时，用不同模型分管不同文件夹（分散索引内存），并用排除规则过滤表情包/缩略图等噪音，从根源降低内存与检索干扰。

## 5. 源码运行与打包

### Windows

环境要求：Python 3.9+（推荐 conda）：

```powershell
git clone https://github.com/Just-A-Freshman/VimgFind.git
cd VimgFind
conda create -n vimgfind python=3.12 && conda activate vimgfind
pip install -r requirements.txt
python ./main.py
```

自行打包：

```powershell
pip install pyinstaller==6.2
pyinstaller -D main.py -i config/data/favicon.ico -w
```

打包完成后，将 `config/data/` 与 `docs/` 文件夹复制到 `_internal` 下即可。

### macOS

详看 `version2.5-macos` 分支的说明文档。



## 6. 更新与反馈

- 更新日志：[VimgFind v2.5.2 更新日志](https://github.com/Just-A-Freshman/VimgFind/releases/tag/program2.5)
- 历史版本：[Releases](https://github.com/Just-A-Freshman/VimgFind/releases)
- 需求与问题：[提交 Issue](https://github.com/Just-A-Freshman/VimgFind/issues)



## 7. 未来规划

- [x] 多模型多索引：不同模型独立索引，自由切换
- [x] macOS 支持



> 详细帮助文档随程序提供（“通用设置 → 帮助文档”），涵盖索引容量、排除规则语法、自定义命令等进阶内容。
