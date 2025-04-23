import socket
import ssl
import traceback

from configs import *

from http_handler import handle_http
from forward_handler import forward_http_request, forward_tcp_tunnel
from cert_handler import get_certificate

from utils import log, get_base_domain

def is_host_proxyed(host: str):
    """检查域名是否匹配允许列表"""
    return True
    # for pattern in PROXY_HOSTS:
    #     if fnmatch.fnmatchcase(host, pattern):
    #         return True
    # return False

def handle_ssl_client(client_socket: socket.socket, domain: str):
    """Handle SSL client connection with optional domain-specific certificate"""
    
    try:
        base_domain = get_base_domain(domain)
        cert_path = get_certificate(base_domain, [base_domain, "*." + base_domain])
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(cert_path, KEY_FILE)
        context.check_hostname = False
        client_ssl_socket = context.wrap_socket(client_socket, server_side=True)
            
        handle_client(client_ssl_socket, with_https=True)
    except Exception as e:
        log(f"SSL handshake failed: {e}")
        client_socket.close()

def handle_client(client_socket: socket.socket, with_https=False):
    try:
        request_raw = b''
        while buf := client_socket.recv(4096):
            request_raw += buf
            if len(buf) < 4096:
                break

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
        
        # 解析请求头
        headers = {}
        for line in request.split('\r\n')[1:]:
            if not line:
                break
            parts = line.split(':', 1)
            if len(parts)!= 2:
                raise ValueError("Invalid HTTP header line")
            headers[parts[0].strip()] = parts[1].strip()

        # 解析请求体 (如果有)
        body = None
        header_end = request.find('\r\n\r\n')
        if header_end != -1:
            body_part = request[header_end+4:]
            is_chunked = 'chunked' in headers.get('Transfer-Encoding', '').lower()
            
            if is_chunked:
                # 处理chunked编码
                body = b''
                chunks = body_part.split('\r\n')
                i = 0
                while i < len(chunks):
                    chunk_size_line = chunks[i]
                    if not chunk_size_line:
                        i += 1
                        continue
                    try:
                        chunk_size = int(chunk_size_line, 16)
                    except ValueError:
                        break
                    if chunk_size == 0:
                        break
                    if i+1 >= len(chunks):
                        break
                    body += chunks[i+1].encode('utf-8')
                    i += 2
            else:
                # 非chunked编码，直接取剩余部分作为body
                body = body_part.encode('utf-8')

        url = None

        if method.upper() == "CONNECT":
            host = path_or_url.split(':')[0]
            port = 443
            if len(path_or_url.split(':')) > 1:
                port = int(path_or_url.split(':')[1])

            client_socket.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                
            if not is_host_proxyed(host):
                log(f"Pass SSL connection to {host}:{port}")
                forward_tcp_tunnel(client_socket, host, port)
            else:
                handle_ssl_client(client_socket, host)
            return
        
        if path_or_url.startswith(('http://', 'https://')):
            url = path_or_url
        else:
            # 如果只有路径，需要从Host头获取主机信息
            host_header = [h for h in request.split('\r\n') if h.startswith('Host:')]
            if not host_header:
                raise ValueError("No Host header in request")
            host = host_header[0][6:].strip()
            url = f"{'https' if with_https else 'http'}://{host}{path_or_url}"

        if not is_host_proxyed(url):
            log(f"Pass HTTP request to {url.geturl()}")
            forward_http_request(client_socket, url.hostname, request)
            return
            
        handle_http(client_socket, url, headers, method, with_https)
    except Exception as e:
        log(f"Error handling client: {e}")
        log(traceback.format_exc())  # 记录堆栈跟踪