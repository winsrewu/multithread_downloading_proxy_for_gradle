import socket
import struct
import select
from typing import Tuple
from configs import *
from utils import log, logger
from client_handler import handle_client, handle_ssl_client

class Socks5Handler:
    def __init__(self, client_socket: socket.socket):
        self.client_socket = client_socket
        self.remote_socket = None
        self.is_http = False
        self.buffer = b''

    def handle(self):
        try:
            self.client_socket.settimeout(10.0)  # Set connection timeout

            # 1. Version and method negotiation
            version, nmethods = self._recv_initial_request()
            if version != 0x05:
                raise ValueError(f"Unsupported SOCKS version: {version}")
            # log(f"Received SOCKS5 version {version} and {nmethods} methods")

            # Send method selection (0x00 - no authentication)
            self.client_socket.sendall(bytes([0x05, 0x00]))

            # 2. Receive client request
            version, cmd, _, addr_type = self._recv_request()
            if version != 0x05:
                raise ValueError(f"Unsupported SOCKS version: {version}")
            # log(f"Received SOCKS5 request for {cmd} to {addr_type}")

            # Handle different address types
            if addr_type == 0x01:  # IPv4
                addr = socket.inet_ntoa(self.client_socket.recv(4))
            elif addr_type == 0x03:  # Domain name
                domain_length = ord(self.client_socket.recv(1))
                addr = self.client_socket.recv(domain_length).decode('utf-8')
            elif addr_type == 0x04:  # IPv6
                ipv6_bytes = self.client_socket.recv(16)
                if len(ipv6_bytes) != 16:
                    raise ValueError("Invalid IPv6 address length")
                addr = socket.inet_ntop(socket.AF_INET6, ipv6_bytes)
            else:
                raise ValueError(f"Unsupported address type: {addr_type}")

            port = struct.unpack('!H', self.client_socket.recv(2))[0]

            # log(f"Received request for {addr}:{port}")

            # 3. Handle command
            if cmd == 0x01:  # CONNECT
                self._handle_connect(addr, port)
            elif cmd == 0x02:  # BIND
                self._handle_bind(addr, port)
            elif cmd == 0x03:  # UDP ASSOCIATE
                self._handle_udp_associate(addr, port)
            else:
                raise ValueError(f"Unsupported command: {cmd}")

        except Exception as e:
            logger.error(f"SOCKS5 error: {e}")
            self._send_reply(0x05, 0x01)  # General failure
            if self.remote_socket:
                self.remote_socket.close()
            self.client_socket.close()

    def _recv_initial_request(self) -> Tuple[int, int]:
        try:
            
            # Receive version identifier/method selection message
            data = b''
            while len(data) < 2:
                chunk = self.client_socket.recv(2 - len(data))
                if not chunk:
                    raise ValueError("Connection closed during negotiation")
                data += chunk
            
            # Verify protocol version (use bytes comparison)
            if data[0:1] != b'\x05':
                raise ValueError(f"Unsupported SOCKS version: {data[0]}")
            
            # Verify methods length
            nmethods = data[1]
            if len(data) < 2 + nmethods:
                remaining = 2 + nmethods - len(data)
                data += self.client_socket.recv(remaining)
            
            # Check for no-auth method
            methods = data[2:2+nmethods]
            if b'\x00' not in methods:
                raise ValueError("No acceptable authentication methods")
            
            return 5, 1  # SOCKS5 with no-auth
        except socket.timeout:
            raise ValueError("Negotiation timeout")
        except Exception as e:
            logger.error(f"Error during initial request: {e}")
            raise

    def _recv_request(self) -> Tuple[int, int, int, int]:
        # More lenient request handling for HTTPS
        data = b''
        while len(data) < 4:
            chunk = self.client_socket.recv(4 - len(data))
            if not chunk:
                raise ValueError("Connection closed prematurely")
            data += chunk
        return data[0], data[1], data[2], data[3]  # version, cmd, rsv, addr_type

    def _handle_connect(self, addr: str, port: int):
        try:
            # Determine address family
            if ':' in addr:  # IPv6
                family = socket.AF_INET6
            else:  # IPv4
                family = socket.AF_INET
            
            self.remote_socket = socket.socket(family, socket.SOCK_STREAM)
            self.remote_socket.settimeout(10.0)  # Set connection timeout
            # log(f"Connecting to {addr}:{port}")
            try:
                self.remote_socket.connect((addr, port))
                if not self.client_socket._closed:  # Check if client still connected
                    self._send_reply(0x00, 0x00)  # Success
                else:
                    logger.error("Client disconnected before reply could be sent")
            except socket.timeout:
                logger.error(f"Connection timeout to {addr}:{port}")
                raise

            # Detect traffic type (HTTP or HTTPS)
            self._detect_traffic_type()

            if self.is_http:  # Handle both HTTP and HTTPS
                # Check if it's HTTPS (TLS) or plain HTTP
                if len(self.buffer) >= 3 and self.buffer[0] == 0x16 and self.buffer[1] == 0x03:
                    # log("Wrapping HTTPS connection with SSL")
                    handle_ssl_client(self.client_socket, addr)
                else:
                    # log("Handling as HTTP proxy")
                    handle_client(self.client_socket, existing_buf=self.buffer[:])
                self.buffer = b''  # Clear buffer after handling client
            else:
                # Direct forwarding for non-HTTP traffic
                self._transfer_data()
        except socket.gaierror as e:
            logger.error(f"Address resolution failed for {addr}:{port}: {e}")
            self._send_reply(0x05, 0x04)  # Host unreachable
            raise
        except Exception as e:
            logger.error(f"Connection failed to {addr}:{port}: {e}")
            self._send_reply(0x05, 0x04)  # Host unreachable
            raise

    def _detect_traffic_type(self):
        """Detect traffic type (HTTP/HTTPS) by peeking at the first few bytes"""
        try:
            # Peek at the first 16 bytes without consuming them
            data = self.client_socket.recv(16, socket.MSG_PEEK)
            self.buffer += data
            # log(f"Received {data}")
            
            # Check for TLS/SSL handshake (HTTPS)
            if len(data) >= 3 and data[0] == 0x16 and data[1] == 0x03:
                self.is_http = True  # Actually HTTPS but we'll handle similarly
                return
                
            # Check for plain HTTP methods
            if len(data) >= 7:  # Minimum for HTTP methods
                first_line = data.decode('utf-8', errors='ignore').split('\r\n')[0]
                if first_line.startswith(('GET ', 'POST ', 'PUT ', 'DELETE ', 'HEAD ', 'OPTIONS ', 'CONNECT ')):
                    self.is_http = True
                    return
                    
            self.is_http = False
        except Exception as e:
            log(f"Traffic detection error: {e}")
            self.is_http = False

    def _send_reply(self, rep: int, _: int, bind_addr: str = '0.0.0.0', bind_port: int = 0):
        """Send SOCKS5 reply with optional bind address and port"""
        ver = 0x05
        rsv = 0x00
        
        # Determine address type
        if ':' in bind_addr:  # IPv6
            addr_type = 0x04
            bnd_addr = socket.inet_pton(socket.AF_INET6, bind_addr)
        else:  # IPv4
            addr_type = 0x01
            bnd_addr = socket.inet_aton(bind_addr)
            
        # Pack port number
        port_bytes = struct.pack('!H', bind_port)
            
        reply = bytes([ver, rep, rsv, addr_type]) + bnd_addr + port_bytes
        self.client_socket.sendall(reply)

    def _handle_bind(self, addr: str, port: int):
        """Handle BIND command (0x02) for reverse connections"""
        try:
            # Create listening socket
            bind_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            bind_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            bind_socket.bind(('0.0.0.0', 0))  # Bind to any available port
            bind_socket.listen(1)
            
            # Get bound address and port
            bind_addr, bind_port = bind_socket.getsockname()
            
            # Send first reply (server listening)
            self._send_reply(0x00, 0x00, bind_addr, bind_port)
            
            # Wait for incoming connection
            self.remote_socket, _ = bind_socket.accept()
            bind_socket.close()
            
            # Send second reply (connection established)
            remote_addr, remote_port = self.remote_socket.getpeername()
            self._send_reply(0x00, 0x00, remote_addr, remote_port)
            
            # Start data transfer
            self._transfer_data()
            
        except Exception as e:
            log(f"BIND command failed: {e}")
            self._send_reply(0x05, 0x01)  # General failure
            raise

    def _handle_udp_associate(self, addr: str, port: int):
        """Handle UDP ASSOCIATE command (0x03) for UDP forwarding"""
        try:
            # Create UDP socket
            udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            udp_socket.bind(('0.0.0.0', 0))  # Bind to any available port
            
            # Get bound address and port
            udp_addr, udp_port = udp_socket.getsockname()
            
            # Send reply with UDP endpoint info
            self._send_reply(0x00, 0x00, udp_addr, udp_port)
            
            # Set client socket to non-blocking for UDP association
            self.client_socket.setblocking(False)
            
            # UDP association loop
            while True:
                r, _, _ = select.select([self.client_socket, udp_socket], [], [], 10.0)
                
                if self.client_socket in r:
                    # Client sent data (should be empty in SOCKS5 UDP)
                    data = self.client_socket.recv(4096)
                    if not data:  # Connection closed
                        break
                
                if udp_socket in r:
                    # Forward UDP datagram to client
                    data, addr = udp_socket.recvfrom(4096)
                    self.client_socket.sendall(data)
                    
        except Exception as e:
            log(f"UDP ASSOCIATE failed: {e}")
            self._send_reply(0x05, 0x01)  # General failure
            raise
        finally:
            udp_socket.close()

    def _transfer_data(self):
        """Direct forwarding for non-HTTP traffic"""
        while True:
            r, _, _ = select.select([self.client_socket, self.remote_socket], [], [])
            for sock in r:
                data = sock.recv(4096)
                if not data:
                    return
                if sock is self.client_socket:
                    self.remote_socket.sendall(data)
                else:
                    self.client_socket.sendall(data)

def handle_socks5_client(client_socket: socket.socket):
    handler = Socks5Handler(client_socket)
    handler.handle()
