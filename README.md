# VimgFind
## 1. 简介
基于AI的本地以图搜图工具直接改编自：[项目地址](https://github.com/Sg4Dylan/EfficientIR)
注意：
- 新版本还支持了【以文搜图】，但由于它必须使用文字编码模型且模型更大，程序运行时会显著地占用更多内存。它的源代码在分支【main2】中；
- 你可以选择下载只包含【以图搜图】功能的版本。它的体积更小，运行时更轻，速度更快。它的源代码在分支【main】中；
- 项目暂时只适配Windows系统，因为代码中包含的一些实现利用了Windows的API
<img width="1028" height="1330" alt="image" src="https://github.com/user-attachments/assets/791cfc1c-bbb9-45cd-b9fd-7dde3d6c6d7f" />


## 2. 特性
### 1. 优点
- 精确！因为使用了高维向量+AI，其匹配精度相当高，即便是图像翻转或局部，都能有很好的搜索效果；
- 查询速度快！因为使用HNSW作为高维向量的索引，匹配速度出色！
- 构建索引的速度快！使用多线程加快了IO速度；作为参考，3GB的图片完全可以在1min内完成索引。

### 2. 缺陷
- 高维向量意味着向量的占用体积更大。一般而言，索引3000张图片可能就会吃掉14MB的空间了；
- 频繁删除或移动文件会会导致索引中有大量无效索引。无效索引会占用磁盘空间，并影响索引速度；
- 更高的内存要求。HNSW索引需要将整个索引加载到内存中才能发挥其搜索优势。这意味着当索引图片大到一定程度可能会爆内存！作为参考，10万张图片就要吃掉约480MB的内存空间。这还是考虑没有无效索引的情况。

## 3. 使用
### 1. 自己搭建配置
需要至少3.8以上的Python环境！
1. 请先在release中下载好AI模型，在config文件夹下新建一个models文件夹，并将模型放到models文件夹下；[下载地址](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/imagenet-b2-opti.onnx)
3. 使用如下命令配置环境```pip install -r requirements.txt```
4. 双击main.py即弹出UI界面

### 2. Windows系统下的可执行程序
1、以图搜图版本
- (1) [Release下载链接](https://github.com/Just-A-Freshman/VimgFind/releases/download/program/v1.2.7z)
- (2) [蓝奏云下载链接](https://wwbbm.lanzouv.com/icIG03d4i74f)  密码:9bo4

2、以图搜图+以文搜图版本
- (1) [Release下载链接](https://github.com/Just-A-Freshman/VimgFind/releases/download/new_program/v2.1.7z)
- (2) [夸克网盘下载](https://pan.quark.cn/s/8e43e327686f)   提取码：bzPQ
  
