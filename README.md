# 基于AI的本地版以图搜图
## 1. 简介
<img width="610" height="419" alt="image" src="https://github.com/user-attachments/assets/07aad6f0-351b-48b6-9518-de4792331032" />

VimgFind是一个Windows平台上的，基于AI模型构建的以图搜图项目，同时具备了以文搜图的能力。界面使用Python的tkinter所写，经过ttkbootstrap的简单美化，具有相对友好的界面可供使用。

1. 优点：
- 匹配精度较高，这是基于传统的图像哈希相似度计算而言的；
- 通过多线程提升索引速度，因此建立索引的速度相对较快；
- 搜索速度快。使用HNSW作为向量索引；

2. 缺点：
- 索引占用磁盘空间相对较大，参考：400张图片约占1MB的磁盘空间；
- 占用内存较高。启动该程序需要占用较多内存；
- 功能相对简陋；

## 2. 源码部署
请确保你的Python版本在3.9及以上。
1. 使用Git将仓库克隆到本地：
    ```
    git clone https://github.com/Just-A-Freshman/VimgFind.git
    ```
2. 随后，进入该文件夹，创建并激活虚拟环境：
    ```
    cd VimgFind
    python -m venv env
    env/Scripts/Activate.ps1
    ```

3. 安装依赖：
    ```
    pip install -r requirements.txt
    ```

4. 启动程序：
    ```
    .\main.py
    ```

请注意，此时虽然可以启动程序，但由于缺乏模型是无法进行搜图的，具体表现为无论怎么更新索引都是立即更新完成，但索引文件为空。请自行下载模型并放置到```config/models```下。下面是两个可供选择的模型和配置文件。

1. 默认的setting.json是【以图搜图+以文搜图】的配置。如果选择使用该配置，请下载该模型：[chinese_clip](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/chinese_clip_onnx.7z)
2. 如果只希望配置简单的【以图搜图】，将config文件夹中的settingv1.1.json替换原来的setting.json文件夹，然后下载imagenet-b2模型：[imagenet](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/imagenet-b2-opti.onnx)

## 3. 打包程序下载地址
### 最新版本(2.3)
[以图搜图v2.3](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.3/v2.3.7z)

### 从2.2迁移
如果你下载过2.2的版本，你可以直接下载下面这个exe程序，然后将其放到2.2版本的文件夹中。
[exe可执行文件](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.3/VimgFind2.3.7z)

### 历史版本
1. [以图搜图V2.2](https://github.com/Just-A-Freshman/VimgFind/releases/download/programv2.2/v2.2.7z)：
恢复了剪切板搜图，增加了【图标预览模式】，【返回结果数控制】，右键菜单【另存为】功能
2. [以图搜图V2.1](https://github.com/Just-A-Freshman/VimgFind/releases/download/new_program/v2.1.7z)
增加以文搜图(回车键触发)，但无剪切板搜图功能
3. [以图搜图V1.2](https://github.com/Just-A-Freshman/VimgFind/releases/download/program/v1.2.7z)
增加剪切板搜图搜图功能
4. [以图搜图V1.1](https://github.com/Just-A-Freshman/VimgFind/releases/download/program/v1.1.zip)
具备基本的以图搜图功能

