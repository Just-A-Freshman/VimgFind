import time, sys
start = time.time()
from controllers import AppController
app = AppController()
def beat():
    print(f"[{time.time()-start:.1f}s] alive search_tools={app.search_tools is not None}", flush=True)
    app.view.after(20000, beat)
app.view.after(20000, beat)
app.view.mainloop()
