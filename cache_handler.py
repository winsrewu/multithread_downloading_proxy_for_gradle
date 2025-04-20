import hashlib
from pathlib import Path
import threading
import time

from configs import *
from utils import log

memory_cache = {}
current_memory_size = 0

def get_cache_key(url):
    """生成URL的缓存键"""
    return hashlib.sha256(url.encode()).hexdigest()

def check_disk_space():
    """检查磁盘空间是否充足"""
    if not Path(CACHE_DIR).exists():
        return True
    used = sum(f.stat().st_size for f in Path(CACHE_DIR).glob('*') if f.is_file())
    return used < DISK_CACHE_MAX_SIZE

def save_to_cache(url, data):
    """保存数据到缓存系统"""
    cache_key = get_cache_key(url)
    
    # 内存缓存
    global current_memory_size
    data_size = len(data)
    
    if data_size <= MEMORY_CACHE_MAX_SIZE:
        # 如果内存不足，清理最旧的缓存
        while current_memory_size + data_size > MEMORY_CACHE_MAX_SIZE and memory_cache:
            oldest_key = next(iter(memory_cache))
            current_memory_size -= len(memory_cache[oldest_key])
            del memory_cache[oldest_key]
        
        memory_cache[cache_key] = {
            'data': data,
            'timestamp': time.time(),
            'size': data_size
        }
        current_memory_size += data_size
    
    # 磁盘缓存 (大于1MB的文件)
    if data_size > 1 * 1024 * 1024 and check_disk_space():
        Path(CACHE_DIR).mkdir(exist_ok=True, parents=True)
        cache_file = CACHE_DIR + "/" + cache_key
        
        try:
            with open(cache_file, 'wb') as f:
                f.write(data)
            # 记录元数据
            with open(f"{cache_file}.meta", 'w') as f:
                f.write(f"timestamp={time.time()}\nsize={data_size}\nurl={url}")
        except Exception as e:
            log(f"Failed to save disk cache: {e}")

def get_from_cache(url):
    """从缓存中获取数据"""
    cache_key = get_cache_key(url)
    now = time.time()
    
    # 检查内存缓存
    if cache_key in memory_cache:
        if now - memory_cache[cache_key]['timestamp'] <= CACHE_EXPIRE_SECONDS:
            log("Cache hit (memory)")
            return memory_cache[cache_key]['data']
        else:
            del memory_cache[cache_key]
    
    # 检查磁盘缓存
    cache_file = CACHE_DIR + "/" + cache_key
    meta_file = CACHE_DIR + "/" + f"{cache_key}.meta"
    
    if Path(cache_file).exists() and Path(meta_file).exists():
        try:
            # 读取元数据
            with open(meta_file) as f:
                meta = dict(line.strip().split('=') for line in f)
            
            if now - float(meta['timestamp']) <= CACHE_EXPIRE_SECONDS:
                # 读取缓存数据
                with open(cache_file, 'rb') as f:
                    data = f.read()
                log("Cache hit (disk)")
                
                # 提升到内存缓存
                if len(data) <= MEMORY_CACHE_MAX_SIZE:
                    save_to_cache(url, data)
                
                return data
            else:
                # 清理过期缓存
                cache_file.unlink()
                meta_file.unlink()
        except Exception as e:
            log(f"Cache read error: {e}")
    
    return None

def clean_cache():
    """定期清理过期缓存"""
    while True:
        time.sleep(3600)  # 每小时清理一次
        now = time.time()
        for cache_file in Path(CACHE_DIR).glob('*.meta'):
            try:
                with open(cache_file) as f:
                    meta = dict(line.strip().split('=') for line in f)
                if now - float(meta['timestamp']) > CACHE_EXPIRE_SECONDS:
                    cache_file.unlink()
                    Path(str(cache_file)[:-5]).unlink()  # 删除对应的数据文件
            except:
                pass

# 启动清理线程
threading.Thread(target=clean_cache, daemon=True).start()