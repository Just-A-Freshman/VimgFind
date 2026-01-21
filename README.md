# 基于AI的本地版以图搜图
## 版本功能预览
- v1.1 基本的以图搜图
- v1.2 增加剪切板搜图
- v2.1 增加以文搜图(回车键触发)，但由于更新顺序原因缺少了剪切板搜图功能
- v2.2 恢复了剪切板搜图，增加了【图标预览模式】，【返回结果数控制】，右键菜单【另存为】功能
- v2.3(最新) 修复了一系列BUG并添加了部分功能，详见release
<img width="610" height="419" alt="image" src="https://github.com/user-attachments/assets/07aad6f0-351b-48b6-9518-de4792331032" />

需要注意，源码及打包程序均仅适用于Windows系统。暂不支持跨平台。

## 源码部署
注意，main分支中的是2.2版本的源码。2.3版本的源码请查看test分支。
请确保你的Python版本在3.9及以上！
将代码clone到本地后，进入项目文件夹下，在控制台输入如下命令安装依赖：
```
pip install -r requirements.txt
```
1. 默认的setting.json是【以图搜图+以文搜图】的配置。如果选择使用该配置，请下载chinese_clip转化为onnx后的模型：[chinese_clip](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/chinese_clip_onnx.7z)
2. 如果只希望配置简单的【以图搜图】，将config文件夹中的settingv1.1.json替换原来的setting.json文件夹，然后下载imagenet-b2模型：[imagenet](https://github.com/Just-A-Freshman/VimgFind/releases/download/model/imagenet-b2-opti.onnx)

将下载好的模型文件放置到./config/models下。双击./main.py即可运行。

## 下载地址
### 最新版本(2.3)
[以图搜图v2.3](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.3/v2.3.7z)

### 从2.2迁移
如果你下载过2.2的版本，你可以直接下载下面这个exe程序，然后将其放到2.2版本的文件夹中。
[exe可执行文件](https://github.com/Just-A-Freshman/VimgFind/releases/download/program2.3/VimgFind2.3.7z)

### 历史版本
1. [以图搜图V2.2](https://github.com/Just-A-Freshman/VimgFind/releases/download/programv2.2/v2.2.7z)
2. [以图搜图V2.1](https://github.com/Just-A-Freshman/VimgFind/releases/download/new_program/v2.1.7z)
3. [以图搜图V1.2](https://github.com/Just-A-Freshman/VimgFind/releases/download/program/v1.2.7z)
4. [以图搜图V1.1](https://github.com/Just-A-Freshman/VimgFind/releases/download/program/v1.1.zip)

