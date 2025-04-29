from enum import Enum
import select
import socket
import ssl
import threading
import time
import traceback
from urllib.parse import urlparse
import requests

from configs import *
import configs
from utils import decode_header, filter_transfer_headers, log, logger
from downloader import download_file_with_schedule, generate_schedule
from log_handler import LoggingSocketDecorator, request_tracker

def _handle_multithread_download(client_socket: socket.socket, target_url: str, headers: dict, method: str, is_ssl: bool, content_length: int, response_headers: dict, response: requests.Response):
    try:
        def safe_send(data):
            try:
                client_socket.sendall(data)
                return True
            except (ConnectionResetError, BrokenPipeError, socket.timeout) as e:
                logger.error(f"Send failed: {type(e).__name__}")
                return False
        
        response_headers["Connection"] = "keep-alive"
        response_headers_raw = f"HTTP/1.1 {response.status_code} {response.reason}\r\n"
        for key, value in response_headers.items():
            response_headers_raw += f"{key}: {value}\r\n"
        response_headers_raw += "\r\n"
        
        safe_send(response_headers_raw.encode())

        schedule = generate_schedule(content_length)
        chunk_num = len(schedule)

        lock = threading.Lock()

        download_process = threading.Thread(
            target=download_file_with_schedule,
            args=(target_url, headers, content_length, schedule, lock),
        )
        download_process.start()

        # Main thread sending loop
        current_chunk_id = 0
        while True:
            with lock:
                if schedule[current_chunk_id]["downloaded"]:
                    if not safe_send(schedule[current_chunk_id]["chunk_data"]):
                        raise Exception("Send failed")
                    schedule[current_chunk_id]["consumed"] = True
                    if not configs.with_cache:
                        schedule[current_chunk_id]["chunk_data"] = None

                    current_chunk_id += 1
                    if current_chunk_id == chunk_num:
                        break

        if result := download_process.join():
            if not safe_send(result):
                raise Exception("Send failed")

        safe_send(b"0\r\n\r\n")

    except Exception as e:
        logger.error(f"Download failed: {e}")
        log(traceback.format_exc())

class InterceptStatus(Enum):
    PASS = 0
    CLOSE_DIRECTLY = 1
    NO_PASS = 2

def _on_header(client_socket: socket.socket, header: bytes, is_ssl: bool):
    method, url, headers = decode_header(header, with_https=False)

    if method != "GET":
        return InterceptStatus.PASS
    
    if headers.get("Range") is not None:
        return InterceptStatus.PASS
    
    content_length = -1
    response_headers = {}
    response = None

    attempts = 1

    # Fetch HEAD
    for attempt in range(attempts):
        try:
            session = requests.Session()
            session.trust_env = DOWNLOADER_TRUST_ENV
            with session.request('HEAD', url, allow_redirects=False, timeout=10, headers=headers, proxies=DOWNLOADER_PROXIES) as head_response:
                content_length = int(head_response.headers.get('Content-Length', -1))
                response_headers = filter_transfer_headers(head_response.headers)
                response = head_response
                if content_length != -1:
                    log(f"Content size: {content_length/1024/1024:.2f}MB")
                else:
                    log("Content size: unknown")
                    return InterceptStatus.PASS
                break
        except Exception as e:
            if attempt == attempts - 1:  # 最后一次尝试失败
                logger.error(f"Head request failed after {attempts} attempts: {e}")
                return InterceptStatus.PASS
            
    log("Using multi-thread download for large file with chunked transfer")

    if content_length >= DOWNLOADER_MULTIPART_THRESHOLD:
        _handle_multithread_download(client_socket, url, headers, method, is_ssl, content_length, response_headers, response)
        return InterceptStatus.CLOSE_DIRECTLY
    
    return InterceptStatus.PASS

def _extract_http_header(data: bytes):
    endpos = -1
    for marker in [b"\r\n\r\n", b"\n\n"]:
        pos = data.find(marker)
        if pos != -1:
            endpos = pos
            if marker == b"\r\n\r\n":
                endpos += 4
            else:
                endpos += 2

            break

    if endpos == -1:
        return None, None
    
    return data[:endpos], data[endpos:]

def _tunnel(client: socket.socket, server: socket.socket, is_ssl: bool):
    sockets = [client, server]
    client_cache = b""

    def flush_cache(no_send=False):
        nonlocal client_cache
        if client_cache and not no_send:
            server.sendall(client_cache)
        client_cache = b""
    
    while True:
        try:
            time.sleep(0.1)
            r, _, _ = select.select(sockets, [], [], 5)
            for sock in r:
                data = b""
                while d := sock.recv(TUNNEL_RECV_SIZE):
                    data += d
                    if len(d) < TUNNEL_RECV_SIZE or len(data) >= TUNNEL_RECV_BUFFER_SIZE:
                        break
                
                if not data:
                    return
                
                if sock is client:
                    client_cache += data
                    
                    if not client_cache.startswith((b"GET", b"POST", b"HEAD", b"PUT", b"DELETE", b"OPTIONS", b"PATCH")):
                        flush_cache()
                        continue
                    
                    header, _ = _extract_http_header(client_cache)
                    if header is None:
                        continue

                    status = _on_header(client, header, is_ssl)
                    if status == InterceptStatus.PASS:
                        flush_cache()
                        continue
                    elif status == InterceptStatus.CLOSE_DIRECTLY:
                        return
                    elif status == InterceptStatus.NO_PASS:
                        flush_cache(no_send=True)
                        continue
                else:
                    client.sendall(data)

        except (socket.error, ConnectionResetError):
            logger.error("Socket error")
            log(traceback.format_exc())
            return

def handle_http(client_socket: socket.socket, url: str, headers: dict, method: str, is_ssl: bool, init_data: bytes):
    # 设置socket超时和缓冲区
    client_socket.settimeout(30)  # 30秒操作超时

    # 记录请求信息
    client_ip, client_port = client_socket.getpeername()
    log(f"New HTTP request from {client_ip}:{client_port} for {url}")

    parsed_url = urlparse(url)

    port = parsed_url.port or (443 if parsed_url.scheme == "https" else 80)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.settimeout(30)  # 30秒操作超时
    server_socket.connect((parsed_url.hostname, port))

    if is_ssl:
        server_socket = ssl.create_default_context().wrap_socket(server_socket, server_hostname=parsed_url.hostname)

    if configs.with_history:
        tracker = request_tracker.init_request(url)
        client_socket = LoggingSocketDecorator(client_socket, tracker)
        server_socket = LoggingSocketDecorator(server_socket, tracker)

    def close_all():
        log(f"Closing sockets of {client_ip}:{client_port} for {url}")
        time.sleep(10)
        if client_socket.fileno() != -1:
            if is_ssl:
                client_socket.unwrap()
            client_socket.close()
        if server_socket.fileno() != -1:
            server_socket.close()

    status = None
    try:
        status = _on_header(client_socket, init_data, is_ssl)
    except Exception as e:
        logger.error(f"Header hook failed: {e}")
        traceback.print_exc()
        close_all()
        return
    
    if status == InterceptStatus.PASS:
        server_socket.sendall(init_data)
    elif status == InterceptStatus.CLOSE_DIRECTLY or status == InterceptStatus.NO_PASS:
        close_all()
        return
        
    try:
        log(f"Starting tunnel from {client_ip}:{client_port} to {parsed_url.hostname}:{port}")
        _tunnel(client_socket, server_socket, is_ssl)
    except Exception as e:
        logger.error(f"Tunnel failed: {e}")
        traceback.print_exc()
    finally:
        close_all()