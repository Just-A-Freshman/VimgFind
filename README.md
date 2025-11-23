# VimgFind
## 简介
基于AI的本地以图搜图工具，直接改编自：[项目地址](https://github.com/Sg4Dylan/EfficientIR)
主要修复了部分一直让我苦恼的Bug并添加了部分功能；
由于水平太次，没有使用原项目使用的QT技术，界面是由tkinter写成的，凑合凑合用吧~
<img width="861" height="1104" alt="image" src="https://github.com/user-attachments/assets/0a1789b8-12ee-43d1-9694-f18dc185922a" />


## 特性
### 1. 优点
- 精确！因为使用了高维向量作为索引，其匹配精度相当高，即便是图像翻转或局部，都能有很好的搜索效果；
- 速度快，使用hwnd进行高维向量的索引，因此匹配速度出色！

### 2. 缺陷
- 正因为使用了高维向量作为索引，其建索引的速度肉眼可见地慢；后续如果有人使用可能考虑使用多进程提速；或提供GPU加速；
- 高维向量意味着向量的占用体积更大。一般而言，1000张图片可能就会吃掉10MB的空间了；
- 频繁删除或移动文件会会导致索引中有大量无效索引，虽然不影响搜索结果，但会影响索引性能(hwnd索引的特性，删除只是标记位置，而且标记位置不一定能被重新占用)

## 使用
### 1. 使用Python环境
需要至少3.8以上的Python环境！
1. 请先在release中下载好AI模型，在config文件夹下新建一个model文件夹，并将模型放到model文件夹下；[下载地址](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/imagenet-b2-opti.onnx)
3. 使用如下命令配置环境```pip install -r requirements.txt```
4. 双击main.py即弹出UI界面

### 2. Windows系统下
打包程序下载地址：
[Windows可执行程序下载](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/default.zip)
