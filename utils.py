import threading

def get_current_thread_name():
    return threading.current_thread().name

def log(message):
    print(f"[{get_current_thread_name()}] [LOG] {message}")