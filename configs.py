import os

# 配置参数 / Configuration parameters
PROXY_HOST = '127.0.0.1'
PROXY_PORT = 27579

# 自签名证书路径 / Self-signed certificate paths
CERT_FILE = "ca_server.crt"
KEY_FILE = "ca_server.key"
CRL_FILE = "crl.pem"  # 证书吊销列表文件 / Certificate Revocation List file
CRL_SERVER_HOST = "127.0.0.1"  # CRL分发服务器主机 / CRL distribution server host
CRL_SERVER_PORT = 27580  # CRL分发服务器端口 没事别瞎改 要不然你就得删缓存了 / CRL distribution server port (Don't change randomly or you'll need to clear cache)
ALWAYS_APPEND_DOMAIN_NAMES = ["*.honkaiimpact3.com"] # 证书强制附加域名 / Force append domain names to certificate

# 下载器阈值 / Downloader thresholds
DOWNLOADER_MAX_THREADS = 32
DOWNLOADER_MULTIPART_THRESHOLD = 1 * 1024 * 1024  # 1MB
DOWNLOADER_PROXIES = {"http": None, "https": None} # deprecated
DOWNLOADER_TRUST_ENV = False # deprecated

# 代理地址 / Proxy URLs
HTTP_PROXY = f"http://{PROXY_HOST}:{PROXY_PORT}"
HTTPS_PROXY = f"http://{PROXY_HOST}:{PROXY_PORT}"
SOCKS5_PORT = 27581  # SOCKS5代理端口 / SOCKS5 proxy port

# 获取 Gradle 用户目录 / Gradle user home directory
GRADLE_USER_HOME = os.getenv("GRADLE_USER_HOME", os.path.expanduser("~/.gradle"))
GRADLE_PROPERTIES_PATH = os.path.join(GRADLE_USER_HOME, "gradle.properties")

# 缓存配置 / Cache configuration
CACHE_DIR = ".cache"  # Cache directory
DISK_CACHE_MAX_SIZE = 10 * 1024 * 1024 * 1024  # 10GB磁盘缓存 / 10GB disk cache max size
DISK_CACHE_MIN_FILE_SIZE = 1024 * 1024  # 缓存区间起点 / Minimum file size to cache
DISK_CACHE_MAX_FILE_SIZE = 256 * 1024 * 1024  # 缓存区间终点 / Maximum file size to cache
CACHE_EXPIRE_SECONDS = 24 * 60 * 60  # 缓存有效期 / Cache expiration time in seconds

with_cache = False  # 是否使用缓存 / Whether to use cache
def set_with_cache(value: bool):
    global with_cache
    with_cache = value

with_history = False  # 是否使用历史记录 / Whether to use history
def set_with_history(value: bool):
    global with_history
    with_history = value

HISTORY_DIR = "log"  # 历史记录目录 / History directory
HISTORY_DIVIDER_H1 = "##=============##"
HISTORY_DIVIDER_H2 = "==========="

# socket配置 / Socket configuration
CLIENT_SOCKET_MAX_CACHE_SIZE = 64 * 1024  # 客户端缓存区最大值 / Maximum size of client socket cache

# tunnel配置 / Tunnel configuration
TUNNEL_RECV_SIZE = 4096  # 隧道接收一级缓存区大小 / Tunnel receive level 1 buffer size
TUNNEL_RECV_BUFFER_SIZE = 1024 * 1024  # 隧道接收二级缓存区大小 / Tunnel receive level 2 buffer size