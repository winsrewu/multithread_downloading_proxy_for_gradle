import select
import socket

from utils import log

def tunnel(client_socket, remote_socket):
    sockets = [client_socket, remote_socket]
    while True:
        try:
            # 使用select等待可读的socket
            readable, _, _ = select.select(sockets, [], [], 1)
            
            for sock in readable:
                data = sock.recv(4096)
                if not data:
                    return
                    
                if sock is client_socket:
                    # 从客户端接收的数据转发到远程服务器
                    remote_socket.send(data)
                else:
                    # 从远程服务器接收的数据转发到客户端
                    client_socket.send(data)
        except (socket.error, select.error) as e:
            print(f"[!] Tunnel error: {e}")
            return
        except Exception as e:
            print(f"[!] Unexpected error in tunnel: {e}")
            return

def forward_tcp_tunnel(client_socket, target_host, target_port):
    """直接转发TCP流量（用于HTTPS）"""
    target_socket = None
    try:
        target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target_socket.connect((target_host, target_port))
        log(f"已连接到目标服务器: {target_host}:{target_port}")

        tunnel(client_socket, target_socket)

        client_socket.unwrap()
        log(f"已断开与客户端的连接")
    except Exception as e:
        log(f"TCP转发失败: {e}")
    finally:
        if target_socket:
            target_socket.close()
        client_socket.close()

def forward_http_request(client_socket, target_host, request):
    """直接转发HTTP请求"""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as target_socket:
            target_socket.connect((target_host, 80))
            target_socket.sendall(request.encode())
            
            while True:
                response = target_socket.recv(4096)
                if not response:
                    break
                client_socket.sendall(response)
                if len(response) < 4096:
                    break
    except Exception as e:
        log(f"HTTP转发失败: {e}")
    finally:
        client_socket.close()
