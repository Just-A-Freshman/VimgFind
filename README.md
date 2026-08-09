# VimgFind

## 1. 项目简介

VimgFind 是一款适用于 Windows 和 Macos 平台的本地 AI 搜图工具，集成**以图搜图**与**以文搜图**（搜索框内按回车键触发）功能，兼顾性能与易用性。

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

### Windows用户

以下给出2.5.2版本的**完整程序**的下载链接：

- Github：[Github下载VimgFind-v2.5.2](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-win64.zip)
- 蓝奏云：[蓝奏云下载VimgFind-v2.5.2](https://wwbbm.lanzouv.com/iKpAQ40w561e)



以下给出更新程序的下载链接：

- Github：[Github下载VimgFind-v2.5.2更新包](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.2-win64-update.zip)
- 蓝奏云：[蓝奏云下载VingFind-v2.5.2更新包](https://wwbbm.lanzouv.com/ikIpA40w58di)

>tip：使用VimgFind 1.2 到 2.4的所有版本的程序，均可使用上述更新程序进行升级。升级方法：点击`更新请点我.hta`，选择目标可执行程序后点击更新即可。更新期间，会弹出黑色的命令行窗口以执行更新脚本，此时请不要关闭窗口。2.5.1版本，在设置界面点击检查更新，无需手动操作即可完成更新。



### Macos用户

我们仅提供一种下载方式，打开终端，执行如下命令：

```sh
/bin/bash -c "$(curl -fsSL https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/install-remote.sh)"
```

执行完成后等待下载，下载完成后会自动启动界面，在APP中可以看到它。

>注意：请不要手动在Release中下载dmg文件；由于Macos系统的默认下载方式会没有签名的APP进行强制隔离，导致APP无法打开；而使用curl这类下载工具可以绕过这一限制。



更新日志请查看：[VimgFindv2.5.1更新日志](https://github.com/Just-A-Freshman/VimgFind/releases/tag/program2.5)

其他历史版本请自行查看：[Releases · Just-A-Freshman/VimgFind/releases](https://github.com/Just-A-Freshman/VimgFind/releases)



### 3.2 源码运行

### Windows系统

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



### Macos系统

详看：`version2.5-macos`分支的说明文档。



### 3.4 模型与配置说明

所有模型配置见：@models.json，里面包含了内置模型的基本配置。如果你希望使用自己的模型，需要：

- 将模型转为onnx格式并启动模型优化；
- 在模型文件夹中编写对应的model.json文件，具体格式可以参考：`config/data/models/实际模型id/model.json`；
- 将文件夹压缩成zip；
- 启动程序，点击模型界面导入使用；

但需要说明，将模型转化成本程序可以接受的有效的onnx模型，其标准步骤尚不清晰，未来将补充详细的转换文档。



## 4. 未来规划

- [x] 引入 [多模型 - 多索引] 机制：用户可以自由切换不同的搜图模型，不同的模型有自己单独的索引文件夹 和 索引文件 
- [x] 增加跨平台支持：计划未来支持Macos系统

其他需求请在issue中提出。

