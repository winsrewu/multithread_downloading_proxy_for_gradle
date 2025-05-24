import socket
import ssl
import traceback

from configs import *

from http_handler import handle_http
from cert_handler import get_certificate

from utils import decode_header, log, get_base_domain, logger

def handle_ssl_client(client_socket: socket.socket, domain: str):
    """Handle SSL client connection with optional domain-specific certificate"""
    
    try:
        base_domain = get_base_domain(domain)
        cert_path = get_certificate(base_domain, [domain] if len(domain.split(".")) > 2 else [base_domain, "*." + base_domain])
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(cert_path, KEY_FILE)
        context.check_hostname = False
        client_ssl_socket = context.wrap_socket(client_socket, server_side=True)
            
        handle_client(client_ssl_socket, with_https=True)
    except Exception as e:
        logger.error(f"SSL handshake failed: {e}")
        client_socket.close()

def handle_client(client_socket: socket.socket, with_https=False, existing_buf=b''):
    try:
        request_raw = existing_buf
        while buf := client_socket.recv(4096):
            request_raw += buf
            if len(buf) < 4096:
                break

        # Try UTF-8 first, fallback to ISO-8859-1 if fails
        try:
            request = request_raw.decode('utf-8')
        except UnicodeDecodeError:
            request = request_raw.decode('iso-8859-1')
            
        if not request:
            log("Received empty request, closing socket.")
            client_socket.close()
            return

        method, url, headers = decode_header(request_raw, with_https)

        if method.upper() == "CONNECT":
            host = headers["Host"]
            if not host:
                raise ValueError("No Host header in CONNECT request")

            client_socket.send(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                
            handle_ssl_client(client_socket, host.split(":")[0])
            return
            
        handle_http(client_socket, url, headers, method, with_https, request_raw)
    except ssl.SSLError as e:
        if 'shutdown while in init' in str(e).lower():
            logger.warning("SSL handshake interrupted by client")
        else:
            logger.error(f"SSL Error: {e}")
    except Exception as e:
        logger.error(f"Error handling client: {e}")
        log(traceback.format_exc())  # 记录堆栈跟踪