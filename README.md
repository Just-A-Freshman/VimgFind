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
### 2.1 核心优势

- 高效的索引构建：通过多线程优化，大幅提升索引生成效率；

- 强大的搜索速度与精度：借助 HNSW 向量索引特性，实现毫秒级搜图，且保持极高的向量召回率；

- 高效的索引重建（2.5版本）：通过算法智能判断索引重建情形，索引**软重建**的情况下可达到 1000个向量 / 秒；

- 多种模型适配（2.5版本）：提供已经经过转化直接可用的几个模型，可随时根据条件切换使用；



### 2.2 固有局限

- 磁盘占用：索引文件体积相对较大，参考数据：400 张图片对应约 1MB 磁盘空间；
- 内存消耗较大：
    - 模型方面：如果使用如Chinese clip模型，启动后预计需占用1.6GB内存；而最轻的模型（仅以图搜图，2.5版本安装包内置）：Osnet，大约启动需消耗170MB内存；
    - 索引方面：HNSW需要将整个索引加载到内存中以支持高效匹配。参考内存消耗：100万张图片 ~ 6-8GB内存。因此更为合适的做法是使用合适模型索引不同的文件夹，以分担内存压力。



## 2.3 其他情况说明

- 2.5版本引入了[多模型 - 多索引]机制，模型和索引是一一对应的。因此，当你切换模型时，索引文件夹也会发生相应的变化。这是正常的，当模型切换回原来的模型，即可看到原来的索引文件夹内容。
- 2.5版本，不再内置Chinese-clip模型，你需要到模型选项卡自行下载；如果程序内置的下载速度过慢，你可以选择复制其中的下载链接进行手动下载。下载完成后，选择加载本地模型即可。
- 模型列表中，只有**多模态**模型支持以文搜图，目前仅提供Chinese-clip一种（作者尝试了不少其他模型，中文效果都不太好）；
- 索引重建：2.5版本，切换到[索引]选项卡，鼠标移动到[当前索引的图片数：XX]上方，可以看到当前无效索引的数量及占比。程序不会主动进行索引重建，需要你在无效索引占比较高时（建议在20%以上时）手动点击重建。不过正如前面所说，索引重建进行了高效的实现，你可以放心大胆地点击它。
- 搜索时，筛选的逻辑是在返回结果中进行的。因此，如果显示筛选条件过严时，优先点击右上角的“...”按钮，将返回结果数调高。


## 3. 快速上手

### 3.1. 直接使用
以下给出2.5版本的下载链接：

- Github的Release页面：https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.5/VimgFind-2.5.1-win64.zip
- 蓝奏云：https://wwbbm.lanzouv.com/iDfGP3w92ltc

增量更新程序将在后续推出。

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



## 4. 未来规划

- [x] 引入 [多模型 - 多索引] 机制：用户可以自由切换不同的搜图模型，不同的模型有自己单独的索引文件夹 和 索引文件 

- [ ] 增加跨平台支持：计划未来支持Macos和Linux系统

其他需求请在issue中提出

