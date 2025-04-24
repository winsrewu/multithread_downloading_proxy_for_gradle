import threading
import time

def get_current_thread_name():
    return threading.current_thread().name

def log(message: str):
    print(f"[{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())}] [{get_current_thread_name()}] [LOG] {message}")

def get_base_domain(domain: str):
    """Extract base domain (second-level domain) from given domain"""
    parts = domain.lower().split('.')
    if len(parts) > 2:
        return '.'.join(parts[-2:])
    return domain

def filter_transfer_headers(headers: dict):
    """
    Filter out headers that are related to transfer encoding, such as Content-Encoding, Transfer-Encoding, etc.
    """
    transfer_related_headers = ['Transfer-Encoding']
    filtered_headers = {k: v for k, v in headers.items() if k not in transfer_related_headers}
    return filtered_headers