# VimgFind

<div align="center">

**本地 AI 搜图工具 · 以图搜图 · 以文搜图**

支持平台：Windows · macOS

[English](./README.en.md) · [更新日志](https://github.com/Just-A-Freshman/VimgFind/releases/tag/program2.5)

</div>



公告：该公告面向使用时间至少大于2周的用户。

作者正在评估为 [排除规则] 增加"作用域"的价值——即让某条规则只对部分索引文件夹生效，而非全局生效。在动手之前，我们想先了解这个需求在真实使用中的普遍程度，避免为低频场景增加所有用户的配置负担。
**无论你是否用过排除规则、是否遇到过相关困扰，你的回答都同样有价值。**
一道单选题，60 秒即可完成：[参与讨论 →](https://github.com/Just-A-Freshman/VimgFind/discussions/17)



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
- **自动更新索引**：程序启动后会系统空闲时（默认 300 秒）自动增量更新索引，不打扰工作。



## 3. 快速上手

### 3.1 安装
**Windows 用户**

- 完整程序：[Github 下载 VimgFind-v2.5.4](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.4-win64.zip) ｜ [蓝奏云下载](https://wwbbm.lanzouv.com/ijeym4aa2pfc)
- 更新程序：[Github 下载 v2.5.4 更新包](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.4-win64-update.zip) ｜ [蓝奏云下载](https://wwbbm.lanzouv.com/iWijn4aa2rla)



**macOS 用户**
> Tip：Macos用户体量非常小，因此目前最新版本还停留在2.5.2；我们仅会在大版本更新时同步Macos的更新；

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



### 3.2 第一次使用

1. **添加索引目录**：进入“索引”选项卡 → 添加你想搜索的图片文件夹；
2. **更新索引**：点击“更新索引”，程序会扫描目录并将图片编码为向量（首次数万张约需几分钟，多线程并行，可在后台进行）；
3. **开始搜索**：切到“搜索”选项卡，浏览/粘贴/拖拽一张图片，或直接输入文字按回车。

> 从2.5.1开始，打包后的程序仅内置最轻的Osnet模型，以便于分发。然而，小模型的能力有限，如果明确追求更高搜索质量，请务必先切换到模型选项卡，根据描述下载并尝试更为合适的模型！



## 4. 重点说明
### 资源占用

- **磁盘**：索引文件约 400 张图片 / 1 MB，通常可忽略；
- **内存**：启动后内存约占135MB（OSNet）～ 880 MB（Chinese-CLIP）；HNSW 索引需整体加载进内存， 100 万张图（1000维）占用约 4-6 GB；
- **最高限制：**程序默认限制最大索引图片数为100万，超过该限制会出错，除非你修改对应的配置文件——具体看帮助文档。因此，图片量大时，请用不同模型分管不同文件夹（分散索引内存），并用排除规则过滤表情包/缩略图等噪音，从根源降低内存与检索干扰。



### 搜索质量

很多时候，你可能对搜出来的结果不太满意。通常，搜索质量主要受三件事影响（按影响力排序）：**用的模型、索引里的图片质量、以及一次返回多少条结果**。

1. **模型**：好的模型是高质量搜索的起点。软件自带的 Osnet 模型只能保证最基本的搜索体验。如果你对搜索质量要求比较高，强烈建议先切换到“模型”选项卡，**选一个更合适的模型**，然后再添加或更新索引目录。换好后，先搜几张图验证一下，确认基本结果没问题。
2. **索引质量**：如果索引里本身就混了很多无关图片或重复图片，搜索结果自然也会夹杂大量没用的内容。你可以提前设置**排除规则**，在建立索引时就把这些内容剔除掉；此外，过期的索引自然也会让部分图片搜不到。虽然程序有自动更新功能，但目前还不够完善。因此当发现搜不到相关图片，可以尝试手动更新一下索引。
3. **返回结果数**：搜索并不是把索引里的每张图片都从头到尾认真比一遍，而是先快速挑出一批“高相似度的候选结果”。这个“候选名额”就是返回结果数。因此，如果索引里有很多垃圾图，它们可能先把名额占满，真正相似的图片反而没机会出现。**在`...`中把返回结果数调大一些**，相当于多留一些候选位置，真正想要的高相似图片往往更容易被搜出来。





## 5. 源码运行与打包

### Windows

环境要求：Python 3.9+（推荐 conda）：

```powershell
git clone https://github.com/Just-A-Freshman/VimgFind.git
cd VimgFind
conda create -n vimgfind python=3.12
conda activate vimgfind
pip install -r requirements.txt
python ./main.py
```

>Tip：2.5.4版本依赖一个补丁文件以修复BUG。该文件在：@patch/ 下；具体如何使用参见@patch/README.md

### 打包

```powershell
conda activate vimgfind
pip install pyinstaller==6.2
build_exe\build_local.bat
```
打包完成后可在：@dist/main/ 下看到实际产物；

### macOS

详看 `version2.5-macos` 分支的说明文档。



## 6. 更新与反馈

- 更新日志：[VimgFind v2.5.4 更新日志](https://github.com/Just-A-Freshman/VimgFind/releases/tag/program2.5)
- 历史版本：[Releases](https://github.com/Just-A-Freshman/VimgFind/releases)
- 需求与问题：
    - 提交问题：https://github.com/Just-A-Freshman/VimgFind/issues
    - 作者邮箱：Chorgri@outlook.com



## 7. 未来规划
重要性：较高 / 复杂度：中等
- [ ] 增加排除规则的作用范围，并且要能根据某个文件夹看到他的排除规则；
- [x] 程序关闭可以选择收缩到托盘（注意释放资源，避免后台持续占用）或者直接关闭程序。
- [x] 重新设计增量排除规则实际应用效果预览方式；



重要性：较低 / 复杂度：较低

- [ ] 增加更多模型支持



重要性：很高 / 复杂度：很高
- [ ] 索引自动更新加强（程序关闭后仍能保持静默运行，更新线程设置为10时软件在后台未被使用3分钟后则调取1-2线程静默更新 电脑整体未使用30分钟后再调用10线程）—— 使用发现，自动更新较为激进，因此空闲时刻会导致对电脑资源占用过多，因此更新初始时要以更少的线程进行；此外当电脑活跃后要及时终止索引更新；



重要性：很低  / 复杂度：很高

- [ ] 模型Skill，用于指导Agent将任意图像或多模态模型转化成程序可以识别与使用的形式（**）
- [ ] 筛选界面优化（待定，见讨论：https://github.com/Just-A-Freshman/VimgFind/discussions/15）（*）



> 详细帮助文档随程序提供（“通用设置 → 帮助文档”），涵盖索引容量、排除规则语法、自定义命令等进阶内容。
