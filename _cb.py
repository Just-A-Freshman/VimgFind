import tkinter as tk
from ttkbootstrap import Style as BStyle
from PIL import Image
from controllers import AppController

# 1) 直接渲染检查：模拟 __build_images 的勾勾
import views.widgets.checkbox_treeview as cbt
from PIL import ImageDraw, ImageFont

app = AppController()
def check():
    # 2) 完整 CheckboxTreeview: 创建 + 插入 checked 项, 检查 on_img 的勾勾(selectfg)像素
    from views.widgets.checkbox_treeview import CheckboxTreeview
    tv = CheckboxTreeview(app.view, "启用")
    iid = tv.insert("", tk.END, text="测试项", checked=True)
    tv.update_idletasks()
    on = tv._CheckboxTreeview__on_img
    if on is None:
        print("on_img 为空 (图片构建失败)")
    else:
        img = on.image  # PIL Image 或 PhotoImage?
        # PhotoImage -> 无法直接读像素; 检查非空 + 通过 __build_images 逻辑验证
        print(f"on_img 生成: {'是' if on else '否'}, 大小: {on.width()}x{on.height()}")
    tv.destroy()
    app.destroy()
app.view.after(2000, check)
app.view.mainloop()
