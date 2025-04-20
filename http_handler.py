import socket
import traceback
import requests
import ssl

from io import BytesIO
from tqdm import tqdm

from configs import *
from utils import log

from downloader import improved_multi_thread_download

def handle_common(client_socket, target_url):
    client_ip, client_port = client_socket.getpeername()

    try:
        # 获取内容信息 (带重试机制)
        content_length = -1 # -1表示未知长度
        for attempt in range(3):  # 最多重试3次
            try:
                with requests.head(target_url, allow_redirects=True, timeout=10) as head_response:
                    content_length = int(head_response.headers.get('Content-Length', -1))
                    if content_length != -1:
                        log(f"Content size: {content_length/1024/1024:.2f}MB")
                    else:
                        log("Content size: unknown")
                    break
            except Exception as e:
                if attempt == 2:  # 最后一次尝试失败
                    log(f"Head request failed after 3 attempts: {e}")
                    content_length = -1
                continue

        # 选择下载方式并发送响应头
        use_chunked = content_length > THRESHOLD
        if use_chunked:
            # 发送分块传输编码的响应头
            response_headers = (
                "HTTP/1.1 200 OK\r\n"
                "Transfer-Encoding: chunked\r\n"
                "Content-Type: application/octet-stream\r\n"
                "Connection: keep-alive\r\n"
                "Cache-Control: max-age=3600\r\n\r\n"
            )
            client_socket.sendall(response_headers.encode())
        else:
            # 发送固定长度的响应头
            if content_length == -1:
                response_headers = (
                    f"HTTP/1.1 200 OK\r\n"
                    f"Connection: keep-alive\r\n"
                    f"Cache-Control: max-age=3600\r\n\r\n"
                )
            else:
                response_headers = (
                    f"HTTP/1.1 200 OK\r\n"
                    f"Content-Length: {content_length}\r\n"
                    f"Connection: keep-alive\r\n"
                    f"Cache-Control: max-age=3600\r\n\r\n"
                )
            client_socket.sendall(response_headers.encode())

        # 发送响应体
        def safe_send(data):
            try:
                client_socket.sendall(data)
                return True
            except (ConnectionResetError, BrokenPipeError, socket.timeout) as e:
                log(f"Send failed: {type(e).__name__}")
                return False

        if use_chunked:
            log("Using multi-thread download for large file with chunked transfer")
            # 流式处理大文件
            downloaded_bytes = BytesIO(improved_multi_thread_download(target_url))
            downloaded_bytes.seek(0)
            
            with tqdm(total=content_length, unit='B', unit_scale=True, desc="Sending") as pbar:
                while True:
                    chunk = downloaded_bytes.read(163840)  # 160KB chunks
                    if not chunk:
                        break
                    if use_chunked:
                        # 分块编码格式: [长度]\r\n[数据]\r\n
                        chunk_header = f"{len(chunk):X}\r\n".encode()
                        # log(f"Sending chunk: {chunk_header.decode().strip()}")
                        if not safe_send(chunk_header) or not safe_send(chunk) or not safe_send(b"\r\n"):
                            break
                    else:
                        if not safe_send(chunk):
                            break
                    pbar.update(len(chunk))
            
            # 发送分块结束标记
            if use_chunked:# and is_connection_alive():
                safe_send(b"0\r\n\r\n")

        else:
            log("Downloading directly")
            with requests.get(target_url, stream=True, timeout=30) as response:
                response.raise_for_status()
                with tqdm(total=content_length, unit='B', unit_scale=True, desc="Sending") as pbar:
                    for chunk in response.iter_content(chunk_size=16384):
                        if use_chunked:
                            chunk_header = f"{len(chunk):X}\r\n".encode()
                            if not safe_send(chunk_header) or not safe_send(chunk) or not safe_send(b"\r\n"):
                                break
                        else:
                            if not safe_send(chunk):
                                break
                        pbar.update(len(chunk))
            
            # 发送分块结束标记
            if use_chunked:
                safe_send(b"0\r\n\r\n")

    except requests.exceptions.RequestException as e:
        log(f"Request error: {e}")
        error_response = (
            f"HTTP/1.1 502 Bad Gateway\r\n"
            f"Content-Type: text/plain\r\n"
            f"Content-Length: {len(str(e))}\r\n\r\n"
            f"{e}"
        )
        client_socket.sendall(error_response.encode())
        
    except Exception as e:
        log(f"Unexpected error: {type(e).__name__}: {e}")
        traceback.print_exc()
        error_page = """<html><body><h1>500 Internal Server Error</h1>
                      <p>Proxy server encountered an error.</p></body></html>"""
        error_response = (
            "HTTP/1.1 500 Internal Server Error\r\n"
            "Content-Type: text/html\r\n"
            f"Content-Length: {len(error_page)}\r\n\r\n"
            f"{error_page}"
        )
        try:
            client_socket.sendall(error_response.encode())
        except:
            pass
        
    finally:
        # client_socket.unwrap()
        client_socket.close()
        log(f"Connection with {client_ip}:{client_port} closed")

def handle_http(client_socket, url):
    # 设置socket超时和缓冲区
    client_socket.settimeout(30)  # 30秒操作超时
    client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)  # 64KB发送缓冲区
    client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)  # 禁用Nagle算法

    # 记录请求信息
    client_ip, client_port = client_socket.getpeername()
    log(f"New HTTP request from {client_ip}:{client_port} for {url.geturl()}")

    # 验证URL
    if not url.netloc:
        raise ValueError("Invalid URL: No host specified")
    # 构建目标URL
    target_url = f"http://{url.netloc}{url.path}"
    if url.query:
        target_url += f"?{url.query}"

    # 处理请求
    handle_common(client_socket, target_url)