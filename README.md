# VimgFind

## 1. 项目简介

VimgFind 是一款适用于 Windows 平台的本地 AI 搜图工具，集成**以图搜图**与**以文搜图**（搜索框内按回车键触发）功能，兼顾性能与易用性。

核心技术栈：

- 向量索引：采用 HNSW 算法，平衡搜索速度与内存占用

- 界面开发：Python tkinter + ttkbootstrap，分拆搜索/索引界面，简洁美观

- 模型推理：依托 onnxruntime，保障高效推理性能

界面展示：
![image-20260713201627284](https://raw.githubusercontent.com/Just-A-Freshman/image-bed/main/Typora/image-20260713201627284.png)


## 2. 功能特性
### 2.1 核心特性

- 高效的索引构建：通过多线程优化，大幅提升索引生成效率；

- 强大的搜索速度与精度：借助 HNSW 向量索引特性，实现毫秒级搜图，且保持极高的向量召回率；

- 高效的索引重建（>=2.5.1）：通过算法智能判断索引重建情形，索引**软重建**的情况下可达到 1000个向量 / 秒；

- 多种模型适配（>=2.5.1）：提供已经经过转化直接可用的几个模型，可随时根据条件切换使用；

- 自定义右键菜单（>=2.5.2）：允许用户控制右键菜单项的显示、快键键和上下位置（拖拽），且可以通过自定义命令拓展菜单功能；



### 2.2 固有局限

- 磁盘占用：索引文件体积相对较大，参考数据：400 张图片对应约 1MB 磁盘空间；
- 内存消耗较大：
    - 模型方面：如果使用如Chinese clip模型，启动后预计需占用1.6GB内存；而最轻的模型（仅以图搜图，2.5版本安装包内置）：Osnet，大约启动需消耗170MB内存；
    - 索引方面：HNSW需要将整个索引加载到内存中以支持高效匹配。参考内存消耗：100万张图片 ~ 6-8GB内存。因此更为合适的做法是使用合适模型索引不同的文件夹，以分担内存压力。

其他情况详见：config/data/docs/ 帮助文档；

## 3. 快速上手

### 3.1. 直接使用
以下给出2.5.2版本的**完整程序**的下载链接：

- Github：[Github下载VimgFind-v2.5.2](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-win64.zip)
- 蓝奏云：[蓝奏云下载VimgFind-v2.5.2](https://wwbbm.lanzouv.com/iKpAQ40w561e)



以下给出更新程序的下载链接：

- Github：[Github下载VimgFind-v2.5.2更新包](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-win64-update.zip)
- 蓝奏云：[蓝奏云下载VingFind-v2.5.2更新包](https://wwbbm.lanzouv.com/ikIpA40w58di)

> tip：使用VimgFind 1.2 到 2.4的所有版本的程序，均可使用上述更新程序进行升级。升级方法：点击`更新请点我.hta`，选择目标可执行程序后点击更新即可。更新期间，会弹出黑色的命令行窗口以执行更新脚本，此时请不要关闭窗口。2.5.1版本，在设置界面点击检查更新，无需手动操作即可完成更新。

更新日志请查看：[VimgFindv2.5.1更新日志](https://github.com/Just-A-Freshman/VimgFind/releases/tag/program2.5)

其他历史版本请自行查看：[Releases · Just-A-Freshman/VimgFind/releases](https://github.com/Just-A-Freshman/VimgFind/releases)



### 3.2 源码运行

环境要求：Python 3.9 及以上版本，推荐使用conda安装：

1. 克隆仓库到本地（version2.5分支）：

    ```
    git clone https://github.com/Just-A-Freshman/VimgFind.git
    ```

    

2. 进入目录并创建激活虚拟环境(powershell)：

    - 如果是使用conda环境：
        ```
        cd VimgFind
        conda create -n vimgfind python=3.12
        conda activate vimgfind
        ```
    - 如果是使用纯Python环境：
        ```
        cd VimgFind
        python -m venv env
        env/Scripts/Activate.ps1
        ```

3. 安装依赖包：

    ```
    pip install -r requirements.txt
    ```

4. 启动程序：

    ```
    python ./main.py
    ```



如果你希望将程序自行打包使用，可以使用如下命令：

```
pip install pyinstaller==6.2
pyinstaller -D main.py -i config/data/favicon.ico -w
```

打包完成后，将源代码中的`config/data/`和`docs/`文件夹复制到`_internal`下即可。



### 3.4 模型与配置说明

所有模型配置见：@models.json，里面包含了内置模型的基本配置。如果你希望使用自己的模型，需要：

- 将模型转为onnx格式并启动模型优化；
- 在模型文件夹中编写对应的model.json文件，具体格式可以参考：`config/data/models/实际模型id/model.json`；
- 将文件夹压缩成zip；
- 启动程序，点击模型界面导入使用；

但需要说明，将模型转化成本程序可以接受的有效的onnx模型，其标准步骤尚不清晰，未来将补充详细的转换文档。



### 3.5 macOS 环境搭建与已知问题（实测记录）

> 本节为 macOS（macos 分支）实际部署中验证过的关键结论与踩坑记录，改动环境前请先阅读。

**环境要求（务必遵守，勿随意更改）**：

- Python：**python.org 官方 3.12**（自带 Tcl/Tk **8.6**）。
  ⚠️ 不要用 Homebrew / uv（python-build-standalone）/ pyenv 自编译的 Python —— 它们捆绑 **Tk 9.0**，
  与 `tkinterdnd2==0.4.3` 内置的 tkdnd 2.9.3、`ttkbootstrap==1.19.0` **均不兼容**，启动即报
  `cannot find symbol "tkdnd_Init"` 或 combobox `invalid command name ...popdown.f.l`。
- hnswlib：必须用 **conda-forge** 安装（`conda install -c conda-forge hnswlib==0.8.0`）。
- 依赖版本**锁定，禁止升级**：`tkinterdnd2==0.4.3`、`ttkbootstrap==1.19.0`（与 Tk 8.6 绑定）。

**无 sudo 场景安装 python.org 3.12（实测可行）**：

```bash
# 1. 下载（国内可换华为云镜像 https://mirrors.huaweicloud.com/python/3.12.9/）
curl -L -o /tmp/python.pkg https://www.python.org/ftp/python/3.12.9/python-3.12.9-macos11.pkg
# 2. 解包（无需 root）
pkgutil --expand-full /tmp/python.pkg /tmp/py3expand
# 3. framework 移入用户目录
mkdir -p ~/Library/Frameworks
mv /tmp/py3expand/Python_Framework.pkg/Payload ~/Library/Frameworks/Python.framework
# 4. 修复硬编码绝对路径（python.org 二进制写死 /Library/Frameworks/...，无 root 时 dyld 找不到）
FRW=$HOME/Library/Frameworks/Python.framework/Versions/3.12
OLD=/Library/Frameworks/Python.framework/Versions/3.12
#    对 framework 下每个 Mach-O（bin、Python、Python.app、lib 下 .so/.dylib）执行：
#    install_name_tool -change $OLD/Python $FRW/Python <文件>
#    install_name_tool -change $OLD/lib/libtcl8.6.dylib $FRW/lib/libtcl8.6.dylib <文件> 等
#    ⚠️ 批量替换时注意：sed 子串替换会把已含用户前缀的路径重复拼接（/Users/x/Users/x/...），需二次清理
# 5. 全部 adhoc 重签（修改 Mach-O 后签名失效，arm64 强制要求签名）
#    codesign --force --sign - <每个 Mach-O>
```

**⚠️ macOS 15+ 的 DYLD 环境变量陷阱（实测）**：

- 新版 dyld **会剥离后台/无 TTY 进程的 `DYLD_*` 环境变量**（nohup、SSH 后台任务、launchd 场景全部失效），
  前台带 TTY 时有效、后台立刻失效，行为不一致。
- 因此**禁止依赖 `DYLD_FRAMEWORK_PATH` / `DYLD_LIBRARY_PATH` 运行应用**；必须用上面的
  `install_name_tool` 把 framework 引用彻底改为用户路径。另需持久化
  `TCL_LIBRARY` / `TK_LIBRARY`（指向 framework 内 `lib/tcl8.6`、`lib/tk8.6`），否则 Tcl 报
  `Can't find a usable init.tcl`。

**Miniforge/conda 安装可能被系统杀（Killed:9）**：解压阶段偶发内存压力被杀，可重试，
或改用轻量的 micromamba 单二进制。

**模型与数据目录（macOS）**：

- 用户数据（首次启动自动从 `config/data` 迁移）：`~/Library/Application Support/VimgFind/`
- 模型目录：`~/Library/Application Support/VimgFind/models/<模型id>/model.onnx`
  （下载 zip 解压后需确保 onnx 文件位于 `<模型id>/` 子目录下，不能直接放在 `models/` 根目录）
- 模型下载地址见 `models.json` 的 `download_url`（Gitee 国内速度更快）。

**国内网络加速**：

- pip 镜像：`-i https://pypi.tuna.tsinghua.edu.cn/simple`
- python.org 安装包：华为云 `https://mirrors.huaweicloud.com/python/<版本号>/`


### 3.6 macOS 打包与分发（实测记录）

**一键构建**（打包 → 缩包 → 签名 → 验证 全流程）：

```bash
./build.sh
```

产物为 `dist/VimgFind.app`（约 120MB）。构建环境默认 `.venv-build`，可用 `BUILD_ENV=xxx ./build.sh` 指定。

**产物结构与启动原理**：

- `.app` 是一个**文件夹**（bundle），Finder 显示为单个图标；右键 → “显示包内容”可查看：
  - `Contents/MacOS/VimgFind`（约 6MB，引导器 + Python 字节码）
  - `Contents/Resources/` + `Contents/Frameworks/`（真正的运行时：onnxruntime/Python/numpy 等，对应 Windows `-D` 的 `_internal`）
- 启动方式：引导器初始化路径 → 加载打包的 Python → 运行 `main.py`。Windows `-F` 的 6MB exe 只是“压缩壳”，真实体积同样 100MB+（运行时解压到临时目录），因此体积并非 macOS 更大。

**默认数据模板（首启自动迁移）**：

- `config/data/` 即打包的默认模板：`setting.json`（干净默认菜单）+ `models/osnet/`（默认模型，`models/` 被 .gitignore 忽略，需自行放入）。
- 全新用户首次启动，程序把模板**复制**到 `~/Library/Application Support/VimgFind/`（复制非移动，bundle 内模板永不减少）；之后用户数据全在用户目录，升级不会被覆盖。
- 模拟全新用户测试（不动本机真实数据）：
  ```bash
  HOME=/tmp/vf_fresh ./dist/VimgFind.app/Contents/MacOS/VimgFind
  rm -rf /tmp/vf_fresh   # 测完即弃
  ```

**签名与分发**：

- 当前为 **ad-hoc 签名**（`com.vimgfind.app`），本机/自测直接运行即可，无任何弹窗。
- 分发给他人时，下载后的 app 会带 `com.apple.quarantine` 属性（下载即被打标），首次打开会被 Gatekeeper 拦截，两种处理：
  - 右键 → 打开 → 再点“打开”（无需终端）
  - 终端执行：`xattr -dr com.apple.quarantine /path/to/VimgFind.app`
- 若希望“下载即可运行”（免上述操作），需 Apple Developer Program（$99/年）→ Developer ID 签名 + notarization 公证（macOS 26 对未公证软件逐步收紧，右键打开通道目前仍可用）。

**构建顺序注意事项**：

- 缩包必须在**签名之前**（缩包移走文件会使签名封存失效）；`build.sh` 已按正确顺序处理。
- 手动构建时参考：`pyinstaller -D -w --name VimgFind --osx-bundle-identifier com.vimgfind.app --add-data "config/data:config/data" --collect-all tkinterdnd2 --collect-all ttkbootstrap main.py` → 缩包（`缩包脚本/shrink_macos.py`）→ `codesign --force --deep --sign - dist/VimgFind.app`。


## 4. 未来规划

- [x] 引入 [多模型 - 多索引] 机制：用户可以自由切换不同的搜图模型，不同的模型有自己单独的索引文件夹 和 索引文件 

- [ ] 增加跨平台支持：计划未来支持Macos和Linux系统

其他需求请在issue中提出

