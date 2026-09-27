import sys

from controllers import AppController
from utils.single_instance import SingleInstance


if __name__ == "__main__":
    lock = SingleInstance()
    if not lock.acquire():
        lock.notify()
        sys.exit(0)
    app = AppController()
    lock.serve(lambda: app.view.after(0, app.activate))  # type: ignore
    app.view.mainloop()
