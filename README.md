# VimgFind

## 1. 项目简介

VimgFind 是一款适用于 Windows 平台的本地 AI 搜图工具，集成**以图搜图**与**以文搜图**（搜索框内按回车键触发）功能，兼顾性能与易用性。

核心技术栈：

- 向量索引：采用 HNSW 算法，平衡搜索速度与内存占用

- 界面开发：Python tkinter + ttkbootstrap，分拆搜索/索引界面，简洁美观

- 模型推理：依托 onnxruntime，保障高效推理性能

界面展示：
<img width="610" height="419" alt="image" src="https://github.com/user-attachments/assets/07aad6f0-351b-48b6-9518-de4792331032" />


## 2. 功能特性
### 2.1 核心优势

- 匹配精度高：相较于传统图像哈希相似度计算，AI 驱动的匹配更精准

- 索引构建快：通过多线程优化，大幅提升索引生成效率

- 搜索响应快：借助 HNSW 向量索引特性，实现毫秒级搜图

### 2.2 已知局限

- 磁盘占用：索引文件体积相对较大，参考数据：400 张图片对应约 1MB 磁盘空间
- 内存消耗：程序启动后占用内存较高，配置较低的设备需留意

## 3. 快速上手

### 3.1. 直接使用（推荐）

#### 测试版

- [v2.4.1 完整包：以图搜图 + 以文搜图](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.4/VimgFind-2.4.1-win64.7z)

#### 稳定版本

- [v2.3.2 完整包：以图搜图+以文搜图](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.3/VimgFind-2.3.2-win64.7z)
- [v2.3.2 完整包：仅以图搜图](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.3/VimgFind-2.3.2-win64-simple.7z)

#### 从2.3 升级到 2.4

- [2.4.1 可执行程序](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.4/VimgFind-2.4.1-win64-update.zip)

将上述文件解压后得到`VimgFind2.4.1.exe`，将其放置到原安装目录下（替代原来的可执行文件）


### 2. 历史版本

所有历史版本请自行查看：[Releases · Just-A-Freshman/VimgFind](https://github.com/Just-A-Freshman/VimgFind/releases)

### 3. 源码运行

环境要求：Python 3.9 及以上版本

1. 克隆仓库到本地（main分支）：

    ```
    git clone https://github.com/Just-A-Freshman/VimgFind.git
    ```

    如果希望克隆测试版本代码，需切换到dev分支：

    ```
    git clone -b dev https://github.com/Just-A-Freshman/VimgFind.git
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

| 模型                                                         | 配置文件                     | 功能描述                          |
| ------------------------------------------------------------ | ---------------------------- | --------------------------------- |
| [chinese_clip](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/chinese_clip_onnx.7z) | config/setting.json          | 默认配置，支持以图搜图 + 以文搜图 |
| [imagenet](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/imagenet-b2-opti.onnx) | config/setting_imagenet.json | 轻量化配置，仅支持以图搜图        |


提示：若未配置模型，程序启动后更新索引会秒完成，但索引文件为空，无法正常搜图。


## 未来规划
1. 增加跨平台支持：计划未来支持Macos和Linux系统 (2.5版本)
2. 引入 [多模型 - 多索引] 机制：用户可以自由切换不同的搜图模型，不同的模型有自己单独的索引文件夹 和 索引文件 (2.5版本)