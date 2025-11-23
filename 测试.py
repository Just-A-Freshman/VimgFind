import tkinter as tk
from tkinter import ttk
import threading
import time
import sys
from queue import Queue
from tqdm import tqdm

# --- 1. 自定义输出流 ---
class QueueStream:
    """
    一个将输出写入到队列的流类。
    """
    def __init__(self, queue: Queue):
        self.queue = queue

    def write(self, message):
        """
        重写 write 方法，将消息放入队列。
        """
        # tqdm 会输出很多空字符串和控制字符，我们可以过滤掉一些
        if message.strip(): 
            self.queue.put(message)

    def flush(self):
        """
        重写 flush 方法，这是一个空操作，因为我们不直接写入文件。
        """
        pass

# --- 2. 高耗时任务 ---
def long_running_task(progress_queue: Queue):
    """
    在单独线程中运行的耗时任务。
    """
    print("任务开始...")
    
    # 将标准输出和标准错误重定向到我们的队列流
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    
    sys.stdout = QueueStream(progress_queue)
    sys.stderr = QueueStream(progress_queue)
    
    try:
        # 模拟一个耗时循环，并用 tqdm 显示进度
        total = 100
        for i in tqdm(range(total), desc="处理中"):
            # 模拟实际的工作
            time.sleep(0.1) 
            
    finally:
        # 任务结束后，恢复原来的输出流
        sys.stdout = original_stdout
        sys.stderr = original_stderr
        progress_queue.put("任务完成！")

# --- 3. UI 相关 ---
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("后台任务进度显示器")
        self.root.geometry("400x300")

        # 创建一个线程安全的队列
        self.progress_queue = Queue()

        # 创建 UI 控件
        self.create_widgets()

        # 启动后台线程
        self.start_background_thread()

        # 开始定期检查队列
        self.check_queue()

    def create_widgets(self):
        """创建 UI 控件"""
        # 创建一个文本框用于显示进度
        self.text_area = tk.Text(self.root, wrap=tk.WORD, state='disabled')
        self.text_area.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # 创建一个滚动条
        scrollbar = ttk.Scrollbar(self.root, command=self.text_area.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_area['yscrollcommand'] = scrollbar.set

    def start_background_thread(self):
        """启动执行耗时任务的后台线程"""
        self.thread = threading.Thread(target=long_running_task, args=(self.progress_queue,))
        # 设置为守护线程，这样当主线程退出时，后台线程也会退出
        self.thread.daemon = True
        self.thread.start()

    def check_queue(self):
        """
        定期检查队列中是否有新消息，并更新 UI。
        这是在 UI 主线程中执行的。
        """
        try:
            # 非阻塞地从队列中获取消息
            while True:
                message = self.progress_queue.get_nowait()
                
                # 更新文本框
                self.text_area.config(state='normal')
                # tqdm 的输出已经包含了换行符，所以直接追加即可
                self.text_area.insert(tk.END, message + "\n")
                self.text_area.see(tk.END)  # 自动滚动到底部
                self.text_area.config(state='disabled')

        except Exception:  # 如果队列为空，会抛出异常，我们忽略它
            pass

        # 100 毫秒后再次调用自己
        self.root.after(100, self.check_queue)

if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()


    