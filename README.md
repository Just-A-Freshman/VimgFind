# VimgFind
## 1. 简介
基于AI的本地以图搜图工具直接改编自：[项目地址](https://github.com/Sg4Dylan/EfficientIR)

请注意：
- 新版本还支持了【以文搜图】，但由于它必须使用文字编码模型且模型更大，程序运行时会显著地占用更多内存。它的源代码在分支【main2】中；
- 你可以选择下载只包含【以图搜图】功能的版本。它的体积明显小得多，运行时更轻，速度更快。它的源代码在分支【main】中；
- 项目只适配Windows系统，因为代码中包含了一些使用了Windows的API的实现，如文件复制和剪切板读取的部分。
<img width="1028" height="1330" alt="image" src="https://github.com/user-attachments/assets/791cfc1c-bbb9-45cd-b9fd-7dde3d6c6d7f" />


## 2. 特性
### 1. 优点
1. 匹配精度高！因为使用了高维向量+AI，其匹配精度相当高，即便是图像翻转或局部，都能有很好的搜索效果；
2. 查询速度快！因为使用HNSW作为高维向量的索引，算法复杂度O(logn)，查询速度几乎不会因为索引图片的增加而下降；
3. 构建索引快！作为参照，本人16GB内存的电脑，索引3GB的高清图片(327张图片)仅用时13s。这是因为程序通过多线程加快了IO速度；线程数可以在配置环境(config/setting.json)中进行调节，默认使用20个线程；

### 2. 缺陷
1. 高维向量意味着向量的占用体积更大。作为参照，索引3000张图片就需要吃掉约14MB的空间；
2. 频繁删除或移动文件会会导致索引中有大量无效索引。无效索引会占用磁盘空间，并影响索引速度；
3. 更高的内存要求。HNSW索引需要将整个索引加载到内存中才能发挥其搜索优势。这意味着当索引图片大到一定程度可能会爆内存！作为参考，10万张图片就要吃掉约480MB的内存空间。这还是考虑没有无效索引的情况。

## 3. 使用
### 1. 源码构建
你需要至少3.8以上的Python环境！

对于只有【以图搜图】功能的版本，首先将分支【main】中的源码克隆到本地，随后你需要：
1. 在release中下载好AI模型```imagenet-b2-opti.onnx```，链接在此；[[下载地址](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/imagenet-b2-opti.onnx)](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/imagenet-b2-opti.onnx)
2. 在项目的config文件夹下新建一个models文件夹，随后将```imagenet-b2-opti.onnx```放置到里面；
3. 在项目的根目录下输入命令：```pip install -r requirements.txt```，等待包安装完成；
4. 双击main.py即弹出UI界面；

对于【以文搜图+以图搜图】的版本，你需要下载分支【main2】中的源码，它的依赖和主分支是一致的，但它需要两个AI模型，一个用于将图片编码成向量；另外一个用于将文字编码成向量，并且它们编码成的向量要在同一个向量空间，这样才能确保文字和图片之间的相似度计算有意义。
1. 下载两个编码模型和词汇表到本地，链接：[https://pan.baidu.com/s/18eBA19kMqdJpP5muV9V18w](https://pan.baidu.com/s/18eBA19kMqdJpP5muV9V18w) 提取码：d30y；
2. 在项目的config文件夹下新建一个clip_model文件夹，随后将这两个模型(image_model.onnx和text_model.onnx)和词汇表(vocab.txt)放置到里面；

剩余步骤和只有【以图搜图】功能的版本一样。

### 2. 直接使用打包程序(Windows系统)
1、以图搜图版本
- (1) [Release下载链接](https://github.com/Just-A-Freshman/VimgFind/releases/download/program/v1.2.7z)
- (2) [蓝奏云下载链接](https://wwbbm.lanzouv.com/icIG03d4i74f)  密码:9bo4

2、以图搜图+以文搜图版本
- (1) [Release下载链接](https://github.com/Just-A-Freshman/VimgFind/releases/download/new_program/v2.1.7z)
- (2) [夸克网盘下载](https://pan.quark.cn/s/8e43e327686f)   提取码：bzPQ


如果你喜欢这个项目，请给我一个star，这对我很重要，谢谢！
