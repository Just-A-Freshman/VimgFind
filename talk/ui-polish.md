# VimgFind → macOS 改造：UI 微调清单（攒集中，最后统一处理）

> 来源：macOS 25.5（M2）+ conda `vimgfind`（Python 3.12 / Tk 8.6）实测反馈。
> 定位：均为视觉/交互微调，不阻塞功能，待主要功能改造完成后统一处理。

| # | 位置 | 问题描述 | 初步判断 |
|---|---|---|---|
| 1 | `views/main_window.py` 通用设置按钮（右上角） | 按钮 padding 过大，压到了下方 Tab 的边框线 | 缩小 padding（`TkS(-2)` 位置或按钮内边距） |
| 2 | `views/widgets/checkbox_treeview.py` CheckboxTreeview 右侧 Checkbutton | 勾勾完全没绘制出来；对比 ttkbootstrap 自带 Checkbutton 勾勾正常 | 自绘 Checkbutton 尺寸过小（勾勾画不出来），需放大或改用 ttk 默认 |
| 3 | `views/model_page.py` 模型 Tab > 模型详情 | 描述 + 下载链接的 Text 组件外边框非常粗且为白色；预期应为无边框、无白色 | `highlightthickness` / `bd` 样式未关或主题背景色覆盖 |

## 处理原则
- 全部为视觉微调，等核心功能（搜索/索引/模型/更新/打包）验收后统一处理；
- 修复后在本机（macOS 25.5）目测确认，重点检查深色主题下的对比度。

## 相关代码线索
- #2：`checkbox_treeview.py` 中 Checkbutton 的绘制（可能用 `checkbutton` 样式或自绘 image，勾勾为绘制矩形/勾形路径）。
- #3：模型详情 Text 组件创建处的 `style`/`config` 参数（`bd=0`、`highlightthickness=0`），以及 ttkbootstrap 主题对 `Text` 的默认处理。
