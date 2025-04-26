import argparse
import socket
import threading
import time
from client_handler import handle_client
from crl_server import start_crl_server

from configs import *

from gradle_handler import set_gradle_proxies, clear_gradle_proxies

from utils import log


def start_proxy(proxy_host, proxy_port, handler, server):
    server.bind((proxy_host, proxy_port))
    server.listen(1000)
    log(f"Proxy listening on {proxy_host}:{proxy_port}")

    # 设置accept超时时间
    server.settimeout(1.0)  # 设置超时时间为1秒

    while True:
        try:
            client_socket, addr = server.accept()
            log(f"Accepted connection from {addr}")
            threading.Thread(target=handler, args=(client_socket,), daemon=True).start()
        except socket.timeout:
            continue  # 如果超时，继续循环

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-cache", action="store_true", help="Enable cache")
    args = parser.parse_args()

    set_with_cache(args.with_cache)

    try:
        set_gradle_proxies(GRADLE_PROPERTIES_PATH)
        
        # Start CRL server in a separate thread
        crl_thread = threading.Thread(
            target=start_crl_server,
            daemon=True,
            name="CRL Server"
        )
        crl_thread.start()

        http_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        threading.Thread(target=start_proxy, args=(PROXY_HOST, PROXY_PORT, handle_client, http_server), daemon=True, name="HTTP Proxy").start()
        while True:
            time.sleep(1)
    finally:
        clear_gradle_proxies(GRADLE_PROPERTIES_PATH)
