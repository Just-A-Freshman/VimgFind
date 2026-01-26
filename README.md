# VimgFind

## 🌟 项目简介

VimgFind 是一款适用于 Windows 平台的本地 AI 搜图工具，集成**以图搜图**与**以文搜图**（搜索框内按回车键触发）功能，兼顾性能与易用性。

核心技术栈：

- 向量索引：采用 HNSW 算法，平衡搜索速度与内存占用

- 界面开发：Python tkinter + ttkbootstrap，分拆搜索/索引界面，简洁美观

- 模型推理：依托 onnxruntime，保障高效推理性能

界面展示：
<img width="610" height="419" alt="image" src="https://github.com/user-attachments/assets/07aad6f0-351b-48b6-9518-de4792331032" />


## 📋 功能特性

### ✅ 核心优势

- 匹配精度高：相较于传统图像哈希相似度计算，AI 驱动的匹配更精准

- 索引构建快：通过多线程优化，大幅提升索引生成效率

- 搜索响应快：借助 HNSW 向量索引特性，实现毫秒级搜图

### ⚠️ 已知局限

- 磁盘占用：索引文件体积相对较大，参考数据：400 张图片对应约 1MB 磁盘空间

- 内存消耗：程序启动后占用内存较高，配置较低的设备需留意

- 功能待完善：暂不支持搜索过滤功能，后续将逐步迭代

## 📦 快速上手

### 1. 直接使用（推荐）

#### 最新版本（v2.3）

下载完整包：[v2.3 完整包](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.3/v2.3.7z)

#### 从 v2.2 版本迁移

无需重新下载完整包，仅更新可执行文件：

下载链接：[v2.3 增量更新包](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.3/VimgFind2.3.7z)

使用方法：将下载的 exe 文件放入 v2.2 版本安装目录，覆盖原有文件即可。

### 2. 历史版本

- **v2.2**：[下载链接](https://github.com/Just-A-Freshman/VimgFind/releases/download/programv2.2/v2.2.7z)
恢复剪切板搜图，新增图标预览模式、返回结果数控制、右键“另存为”功能

- **v2.1**：[下载链接](https://github.com/Just-A-Freshman/VimgFind/releases/download/new_program/v2.1.7z)
新增以文搜图（回车键触发），暂不支持剪切板搜图

- **v1.2**：[下载链接](https://github.com/Just-A-Freshman/VimgFind/releases/download/program/v1.2.7z)
新增剪切板搜图功能

- **v1.1**：[下载链接](https://github.com/Just-A-Freshman/VimgFind/releases/download/program/v1.1.zip)
具备基础以图搜图功能

### 3. 源码运行

环境要求：Python 3.9 及以上版本

1. 克隆仓库到本地：
    ```
    git clone https://github.com/Just-A-Freshman/VimgFind.git
    ```

2. 进入目录并创建激活虚拟环境(powershell)：
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
    env/Scripts/python.exe main.py
    ```

### 🧩 模型与配置说明

源码运行前需手动下载模型，放置于 `config/models` 目录下。配置文件需确保命名为 `setting.json`（非默认名称需手动重命名），具体对应关系如下：

|模型|配置文件|功能描述|
|---|---|---|
|[chinese_clip](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/chinese_clip_onnx.7z)|config/setting.json|默认配置，支持以图搜图 + 以文搜图|
|[imagenet](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/imagenet-b2-opti.onnx)|config/setting_imagenet.json|轻量化配置，仅支持以图搜图|


提示：若未配置模型，程序启动后更新索引会秒完成，但索引文件为空，无法正常搜图。
