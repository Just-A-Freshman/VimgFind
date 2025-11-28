from tkinter.ttk import Notebook, Frame, Entry, Button, Treeview, Label, LabelFrame
import tkinter as tk

from setting import WinInfo


class WinGUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.__win()
        self.switch_tab = self.__set_switch_tab(self)
        self.search_entry = self.__set_search_entry(self.search_tab)
        self.search_button = self.__set_search_button(self.search_tab)
        self.result_table = self.__set_result_table(self.search_tab)
        self.preview_frame1 = self.__set_preview_frame1(self.search_tab)
        self.preview_frame2 = self.__set_preview_frame2(self.search_tab)
        self.preview_canvas1 = self.__set_preview_canvas(self.preview_frame1)
        self.preview_canvas2 = self.__set_preview_canvas(self.preview_frame2)
        self.index_dataset_table = self.__set_index_dataset_table(self.setting_tab)
        self.index_tip_label = self.__set_index_tip_label(self.setting_tab)
        self.add_index_button = self.__set_add_index_button(self.setting_tab)
        self.update_index_button = self.__set_update_index_button(self.setting_tab)
        self.delete_index_button = self.__set_delete_index_button(self.setting_tab)
        self.rebuild_index_button = self.__set_rebuild_index_button(self.setting_tab)

    def __win(self) -> None:
        self.title(WinInfo.title)
        width = WinInfo.width
        height = WinInfo.height
        screenwidth = self.winfo_screenwidth()
        screenheight = self.winfo_screenheight()
        geometry = '%dx%d+%d+%d' % (width, height, (screenwidth - width) / 2, (screenheight - height) / 2)
        self.geometry(geometry)
        self.iconbitmap(WinInfo.ico_path)
        
    def __set_switch_tab(self, parent) -> Notebook:
        frame = Notebook(parent)
        self.search_tab = self.__set_tab_frame(frame)
        frame.add(self.search_tab, text="检索")
        self.setting_tab = self.__set_tab_frame(frame)
        frame.add(self.setting_tab, text="设置")
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        return frame
    
    def __set_tab_frame(self, parent) -> Frame:
        frame = Frame(parent)
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        return frame
    
    def __set_search_entry(self, parent) -> Entry:
        ipt = Entry(parent, )
        ipt.place(relx=0.0093, rely=0.0192, relwidth=0.4889, relheight=0.0690)
        return ipt
    
    def __set_search_button(self, parent) -> Button:
        btn = Button(parent, text="搜索", takefocus=False,)
        btn.place(relx=0.51, rely=0.0192, relwidth=0.115, relheight=0.0690)
        return btn
    
    def __set_result_table(self, parent) -> Treeview:
        columns = {"名称":162, "大小":100, "修改时间": 160 , "相似度":100}
        
        tk_table = Treeview(parent, show="headings", columns=list(columns), selectmode="browse")
        for text, width in columns.items():
            tk_table.heading(text, text=text, anchor='center')
            tk_table.column(text, anchor='center', width=width, stretch=True)
        
        tk_table.place(relx=0.0093, rely=0.1111, relwidth=0.6170, relheight=0.888)
        return tk_table

    def __set_preview_frame1(self, parent) -> LabelFrame:
        frame = LabelFrame(parent, text="源图片")
        frame.place(relx=0.63, rely=0.1, relwidth=0.365, relheight=0.4444)
        return frame
    
    def __set_preview_frame2(self, parent) -> LabelFrame:
        frame = LabelFrame(parent, text="匹配图片")
        frame.place(relx=0.63, rely=0.5555, relwidth=0.365, relheight=0.4444)
        return frame
    
    def __set_preview_canvas(self, parent) -> tk.Canvas:
        canvas = tk.Canvas(parent)
        canvas.place(relx=0, rely=0, relwidth=1, relheight=1)
        return canvas

    def __set_index_tip_label(self, parent) -> Label:
        label = Label(parent,text="当前索引的图库",anchor="nw")
        label.place(relx=0, rely=0.02, relwidth=1, relheight=0.0575)
        return label
    
    def __set_index_dataset_table(self, parent) -> Treeview:
        columns = {" ": 32, "图库目录":628}
        tk_table = Treeview(parent, show="headings", columns=list(columns),)
        for text, width in columns.items():
            tk_table.heading(text, text=text, anchor='center')
            tk_table.column(text, anchor='center', width=width, stretch=True)
        
        tk_table.place(relx=0.0081, rely=0.0881, relwidth=0.7776, relheight=0.9119)
        return tk_table
    
    def __set_add_index_button(self, parent) -> Button:
        btn = Button(parent, text="添加索引目录", takefocus=False,)
        btn.place(relx=0.7974, rely=0.0862, relwidth=0.1921, relheight=0.0862)
        return btn
    
    def __set_update_index_button(self, parent) -> Button:
        btn = Button(parent, text="更新索引目录", takefocus=False,)
        btn.place(relx=0.7974, rely=0.1916, relwidth=0.1921, relheight=0.0862)
        return btn
    
    def __set_delete_index_button(self, parent) -> Button:
        btn = Button(parent, text="删除索引目录", takefocus=False,)
        btn.place(relx=0.7974, rely=0.2969, relwidth=0.1921, relheight=0.0862)
        return btn
    
    def __set_rebuild_index_button(self, parent) -> Button:
        btn = Button(parent, text="重建索引目录", takefocus=False,)
        btn.place(relx=0.7974, rely=0.4022, relwidth=0.1921, relheight=0.0862)
        return btn
    