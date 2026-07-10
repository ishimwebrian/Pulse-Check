import threading
from typing import Callable

def start_monitor_timer(timeout: int, on_expire: Callable[[], None]) -> threading.Timer:
    """
    Starts a daemon thread timer that executes the on_expire callback after timeout seconds.
    """
    timer = threading.Timer(float(timeout), on_expire)
    timer.daemon = True
    timer.start()
    return timer
