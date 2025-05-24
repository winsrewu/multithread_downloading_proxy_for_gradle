import threading
import time
from rich.progress import Progress, BarColumn, DownloadColumn
from rich.console import Console

console = Console()

class Logger:
    """日志记录器"""
    def __init__(self):
        self._console = console
    
    def log(self, message: str):
        """记录普通日志"""
        self._console.print(f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}] [{threading.current_thread().name}] [LOG] {message}")
    
    def error(self, message: str):
        """记录错误日志"""
        self._console.print(f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}] [{threading.current_thread().name}] [ERROR] {message}", style="bold red")

    def warning(self, message: str):
        """记录警告日志"""
        self._console.print(f"[{time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}] [{threading.current_thread().name}] [WARNING] {message}", style="bold yellow")

class ProgressBar:
    """进度条管理类"""
    def __init__(self):
        self._console = console
        self._progress = Progress(
            "[progress.description] {task.description}",
            BarColumn(bar_width=None),
            DownloadColumn(),
            console=self._console,
            refresh_per_second=10
        )
        self._lock = threading.Lock()
        self._count = 0

    def create_task(self, description: str, total: int):
        """创建进度条任务"""
        self._start()
        return self._progress.add_task(description, total=total)

    def update(self, task_id, advance: int):
        """更新进度"""
        self._progress.update(task_id, advance=advance)

    def remove_task(self, task_id):
        """移除任务"""
        self._progress.remove_task(task_id)
        self._stop()

    def _start(self):
        """启动进度条"""
        with self._lock:
            self._count += 1
            if self._count == 1:
                self._progress.start()

    def _stop(self):
        """停止进度条"""
        with self._lock:
            self._count -= 1
            if self._count == 0:
                self._progress.stop()

    def render(self):
        """手动渲染进度条"""
        with self._lock:
            for task_id, description in self._tasks.items():
                task = self._progress.tasks[task_id]
                progress_text = self._progress.get_renderable(task, BarColumn(bar_width=None)).render(self._console, self._console.options)
                self._console.print(description)
                self._console.print(progress_text)
                self._console.print()  # 确保每个任务之间换行

# 全局进度条实例
progress_bar = ProgressBar()

# 全局日志记录器实例
logger = Logger()

def log(message: str):
    """兼容旧代码的日志函数"""
    logger.log(message)

def get_current_thread_name():
    return threading.current_thread().name

def get_base_domain(domain: str):
    """Extract base domain (second-level domain) from given domain"""
    parts = domain.lower().split('.')
    if len(parts) > 2:
        return '.'.join(parts[-2:])
    return domain

def filter_transfer_headers(headers: dict):
    """
    Filter out headers that are related to transfer encoding, which is python will handle automatically.
    """
    transfer_related_headers = ['Transfer-Encoding', 'Content-Encoding']
    filtered_headers = {k: v for k, v in headers.items() if k not in transfer_related_headers}
    return filtered_headers

def decode_header(data: bytes, with_https: bool):
    """
    Decode header data
    """
    # Try UTF-8 first, fallback to ISO-8859-1 if fails
    try:
        header = data.decode('utf-8')
    except UnicodeDecodeError:
        header = data.decode('iso-8859-1')

    first_line = header.split('\r\n')[0].strip()
    parts = [p for p in first_line.split(' ') if p]  # Remove empty strings from split
    if len(parts) < 3:
        raise ValueError(f"Invalid HTTP request line: {first_line}")
    
    method = parts[0]
    path_or_url = parts[1]
    version = ' '.join(parts[2:])  # Handle cases where version contains spaces

    headers = {}
    for line in header.split('\r\n')[1:]:
        if not line:
            break
        parts = line.split(':', 1)
        if len(parts)!= 2:
            raise ValueError("Invalid HTTP header line")
        key = parts[0].strip().lower().capitalize()
        headers[key] = parts[1].strip()

    url = path_or_url

    if not url.startswith(("http://", "https://")):
        # get from host header, ignoring https
        host = headers.get("Host")
        if not host:
            # Try alternative headers
            host = headers.get("X-Forwarded-Host") or headers.get("X-Host")
            if not host:
                raise ValueError("No Host, X-Forwarded-Host or X-Host header in request")
        
        url = f"{'https' if with_https else 'http'}://{host}{path_or_url}"
        
    return method, url, headers
