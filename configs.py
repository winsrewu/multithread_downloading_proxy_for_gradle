import os

# 配置参数
PROXY_HOST = '127.0.0.1'
PROXY_PORT = 3000

# 自签名证书路径
CERT_FILE = "server.crt"
KEY_FILE = "server.key"

# 下载器阈值
THRESHOLD = 10 * 1024 * 1024  # 10MB阈值
MAX_THREADS = 16

# 代理地址
HTTP_PROXY = f"http://{PROXY_HOST}:{PROXY_PORT}"
HTTPS_PROXY = f"http://{PROXY_HOST}:{PROXY_PORT}"  # 注意：HTTPS代理通常使用HTTP代理地址

# 获取 Gradle 用户目录
GRADLE_USER_HOME = os.getenv("GRADLE_USER_HOME", os.path.expanduser("~/.gradle"))
GRADLE_PROPERTIES_PATH = os.path.join(GRADLE_USER_HOME, "gradle.properties")

# 缓存配置
CACHE_DIR = ".cache"
MEMORY_CACHE_MAX_SIZE = 100 * 1024 * 1024  # 100MB内存缓存
DISK_CACHE_MAX_SIZE = 10 * 1024 * 1024 * 1024  # 10GB磁盘缓存
CACHE_EXPIRE_SECONDS = 24 * 60 * 60  # 24小时缓存有效期

# 需要代理的域名列表
PROXY_HOSTS = ["*.mojang.com", "*.minecraft.net"]