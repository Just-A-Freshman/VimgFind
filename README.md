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

**macOS 用户**

**方式 A：命令行自动安装（推荐）**

打开终端，执行以下命令（脚本会先下载到本地，再自动安装并启动应用）：

```sh
curl -fsSL -o /tmp/vimgfind-install.sh https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-macos-install.sh
bash /tmp/vimgfind-install.sh
```

> 安全提示：安装脚本将以你的用户权限在本地执行。建议先查看脚本内容（`cat /tmp/vimgfind-install.sh`）再运行；运行即代表你已知晓并接受相应风险。国内网络若无法访问 GitHub，可改用下方的 dmg 手动安装（Gitee 镜像）。

**方式 B：手动安装（dmg）**

- GitHub：[下载 VimgFind-2.5.2-macos.dmg](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-macos.dmg)
- Gitee 镜像：[下载 VimgFind-2.5.2-macos.dmg](https://gitee.com/Chorgri/VimgFind/releases/download/program2.5/VimgFind-2.5.2-macos.dmg)

打开 dmg，将 `VimgFind.app` 拖入“应用程序”文件夹。若启动时提示“已损坏，无法打开”或“无法验证开发者”（未签名 App 被系统隔离所致），任选其一：

1. 在 Finder 中**右键**点击 `VimgFind.app`，选择“打开”，并在弹窗中确认；
2. 或打开终端执行：`xattr -dr com.apple.quarantine /Applications/VimgFind.app`

安装包校验（可选）：下载后执行 `shasum -a 256` 核对 SHA-256：

```sh
shasum -a 256 VimgFind-2.5.2-macos.dmg
# 期望输出：917960061391634332ac7b7e486d168363e67b8c1ba284a8edb80c92f6ffa79b
```

**Windows 用户**

- 完整程序：[Github 下载 VimgFind-v2.5.2](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-win64.zip) ｜ [蓝奏云下载](https://wwbbm.lanzouv.com/iKQcC41o45qf)
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
