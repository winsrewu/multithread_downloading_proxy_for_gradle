import fnmatch
import socket
import ssl
import threading
import time
from urllib.parse import urlparse
import traceback

from configs import *

from http_handler import handle_http
from gradle_handler import set_gradle_proxies, clear_gradle_proxies
from forward_handler import forward_http_request, forward_tcp_tunnel

from utils import log

proxy_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
proxy_context.load_cert_chain(CERT_FILE, KEY_FILE)
proxy_context.check_hostname = False

def is_host_proxyed(host):
    """检查域名是否匹配允许列表"""
    for pattern in PROXY_HOSTS:
        if fnmatch.fnmatchcase(host, pattern):
            return True
    return False

def handle_ssl_client(client_socket):
    client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")

    client_ssl_socket = proxy_context.wrap_socket(client_socket, server_side=True)
    handle_client(client_ssl_socket)

def handle_client(client_socket):
    try:
        request_raw = client_socket.recv(4096)
        request = request_raw.decode('utf-8', errors='ignore')
        if not request:
            log("Received empty request, closing socket.")
            client_socket.close()
            return

        # 解析请求行
        first_line = request.split('\r\n')[0]
        parts = first_line.split()
        if len(parts) < 3:
            raise ValueError("Invalid HTTP request line")
            
        method, path_or_url, version = parts
        url = None

        if method.upper() == "CONNECT":
            host = path_or_url.split(':')[0]
            port = 443
            if len(path_or_url.split(':')) > 1:
                port = int(path_or_url.split(':')[1])
                
            if not is_host_proxyed(host):
                log(f"Pass SSL connection to {host}:{port}")
                forward_tcp_tunnel(client_socket, host, port)
            else:
                handle_ssl_client(client_socket)
            return
        
        if path_or_url.startswith(('http://', 'https://')):
            url = urlparse(path_or_url)
        else:
            # 如果只有路径，需要从Host头获取主机信息
            host_header = [h for h in request.split('\r\n') if h.startswith('Host:')]
            if not host_header:
                raise ValueError("No Host header in request")
            host = host_header[0][6:].strip()
            url = urlparse(f"http://{host}{path_or_url}")

        if not is_host_proxyed(url.hostname):
            log(f"Pass HTTP request to {url.geturl()}")
            client_socket.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            forward_http_request(client_socket, url.hostname, request)
            return
            
        handle_http(client_socket, url)
    except Exception as e:
        log(f"Error handling client: {e}")
        log(traceback.format_exc())  # 记录堆栈跟踪

def start_proxy(proxy_host, proxy_port, handler, server):
    server.bind((proxy_host, proxy_port))
    server.listen(5)
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
    try:
        set_gradle_proxies(GRADLE_PROPERTIES_PATH)

        http_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        threading.Thread(target=start_proxy, args=(PROXY_HOST, PROXY_PORT, handle_client, http_server), daemon=True, name="HTTP Proxy").start()
        while True:
            time.sleep(1)
    finally:
        clear_gradle_proxies(GRADLE_PROPERTIES_PATH)
