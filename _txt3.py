import tkinter as tk
from controllers import AppController

app = AppController()
def check():
    t = app.view.model_tab.detail_desc_text
    print(f"model detail: highlight={t.cget('highlightthickness')} bd={t.cget('bd')} bg={t.cget('bg')}")
    app.setting_controller.show_dialog()
    def check2():
        sd = app.setting_controller.dialog
        ct = sd.custom_menu_tab.command_text
        print(f"command_text: highlight={ct.cget('highlightthickness')} bd={ct.cget('bd')} bg={ct.cget('bg')}")
        from views.test_dialog import TestResultDialog
        td = TestResultDialog(app.view, [], None)
        td.update()
        tt = td.detail_text
        print(f"test_dialog text: highlight={tt.cget('highlightthickness')} bd={tt.cget('bd')} bg={tt.cget('bg')}")
        td.destroy(); sd.destroy(); app.destroy()
    app.view.after(500, check2)
app.view.after(2000, check)
app.view.mainloop()
