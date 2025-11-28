# VimgFind
## 简介
基于AI的本地以图搜图工具，直接改编自：[项目地址](https://github.com/Sg4Dylan/EfficientIR)
主要修复了部分一直让我苦恼的Bug并添加了部分功能；
由于水平太次，没有使用原项目使用的QT技术，界面是由tkinter写成的，凑合凑合用吧~
<img width="1028" height="1330" alt="image" src="https://github.com/user-attachments/assets/791cfc1c-bbb9-45cd-b9fd-7dde3d6c6d7f" />




## 特性
### 1. 优点
- 精确！因为使用了高维向量+AI，其匹配精度相当高，即便是图像翻转或局部，都能有很好的搜索效果；
- 查询速度快！因为使用hwnd作为高维向量的索引，匹配速度出色！
- 构建索引的速度快！使用多线程加快了IO速度；作为参考，3GB的图片完全可以在1min内完成索引。

### 2. 缺陷
- 高维向量意味着向量的占用体积更大。一般而言，索引1000张图片可能就会吃掉10MB的空间了；
- 频繁删除或移动文件会会导致索引中有大量无效索引。无效索引会占用磁盘空间，并影响索引速度；

## 使用
### 1. 使用Python环境
需要至少3.8以上的Python环境！
1. 请先在release中下载好AI模型，在config文件夹下新建一个model文件夹，并将模型放到model文件夹下；[下载地址](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/imagenet-b2-opti.onnx)
3. 使用如下命令配置环境```pip install -r requirements.txt```
4. 双击main.py即弹出UI界面

### 2. Windows系统下
打包程序下载地址：
[Windows可执行程序下载](https://github.com/Just-A-Freshman/VimgFind/releases/download/program/default.zip)
