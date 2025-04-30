import argparse
from pathlib import Path
import socket
import threading
import time
from client_handler import handle_client
import configs
from crl_server import start_crl_server

from configs import *

from gradle_handler import set_gradle_proxies, clear_gradle_proxies
from log_handler import request_tracker
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
    parser.add_argument("--with-history", action="store_true", help="Enable history")
    parser.add_argument("--gradle", action="store_true", help="Set gradle proxies")
    parser.add_argument("--socks5", action="store_true", help="Enable SOCKS5 proxy")
    args = parser.parse_args()

    set_with_cache(args.with_cache)
    set_with_history(args.with_history)

    try:
        if args.gradle:
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

        if args.socks5:
            from socks_handler import handle_socks5_client
            socks5_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            threading.Thread(target=start_proxy, args=(PROXY_HOST, SOCKS5_PORT, handle_socks5_client, socks5_server), daemon=True, name="SOCKS5 Proxy").start()
        while True:
            time.sleep(1)
    finally:
        if args.gradle:
            clear_gradle_proxies(GRADLE_PROPERTIES_PATH)
        if configs.with_history:
            Path(HISTORY_DIR).mkdir(exist_ok=True)
            request_tracker.dump(HISTORY_DIR + "/" + str(time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())) + "_sort_by_time.log")
            request_tracker.dump(HISTORY_DIR + "/" + str(time.strftime('%Y-%m-%d-%H-%M-%S', time.localtime())) + "_sort_by_size.log",
                                  sort_lambda=lambda x: -x.get_size())
