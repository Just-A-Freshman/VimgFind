import sys, tkinter as tk
from tkinter import filedialog
pattern = sys.argv[1]
root = tk.Tk()
root.withdraw()
def test():
    print("opening dialog with pattern:", pattern, flush=True)
    filedialog.askopenfilenames(filetypes=[("图片文件", pattern)])
    print("dialog returned", flush=True)
root.after(800, test)
root.mainloop()
