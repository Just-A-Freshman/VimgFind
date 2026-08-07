# VimgFind → macOS 改造：UI 微调清单（攒集中，统一处理）

> 来源：macOS 25.5（M2）+ conda `vimgfind`（Python 3.12 / Tk 8.6）实测反馈。
> 定位：均为视觉/交互微调，不阻塞功能，统一处理。

## 处理原则
- 修复后在本机（macOS 25.5）目测确认，重点检查深色主题下的对比度。

---

## 1. 右上角"通用设置"按钮压到 Tab 边框线

- **位置**：`views/main_window.py` 通用设置按钮（右上角）
- **现象**：按钮 padding 过大，压到了下方 Tab 的边框线
- **初步判断**：缩小 padding（`TkS(-2)` 位置或按钮内边距）

## 2. CheckboxTreeview 右侧 Checkbutton 勾勾未绘制

- **位置**：`views/widgets/checkbox_treeview.py`
- **现象**：勾勾完全没绘制出来；对比 ttkbootstrap 自带 Checkbutton 勾勾正常
- **初步判断**：自绘 Checkbutton 尺寸过小（勾勾画不出来），需放大或改用 ttk 默认

## 3. 模型 Tab > 模型详情 Text 组件外边框粗且白色

- **位置**：`views/model_page.py` 模型 Tab > 模型详情（描述 + 下载链接）
- **现象**：Text 组件外边框非常粗且为白色；预期应为无边框、无白色
- **初步判断**：`highlightthickness` / `bd` 样式未关或主题背景色覆盖

## 4. macOS 弹窗按钮顺序：左"取消"、右"确定"

- **规则**：macOS HIG 惯例——按钮对中**取消在左、确定/默认在右**（Windows 相反）。
- **现状**：以下自定义弹窗为"左确定、右取消"，需调换：
  - `views/widgets/simpledialog.py` `BasicDialog.buttonbox`（askstring/askinteger/askfloat 全部输入弹窗）：`btn_save`(col1) + `btn_cancel`(col2) → 应调换
  - `views/search_page.py` 筛选面板底部（123-127 行）：`confirm_btn`(col0) + `cancel_btn`(col1) → 应调换
- **无需处理**：tkinter `messagebox.*`（showinfo/askyesno/askokcancel 等）走系统 NSAlert，
  按钮顺序由 AppKit 自动遵循 macOS 布局（默认按钮在右），代码无法也无需干预。

## 5.（预留）
