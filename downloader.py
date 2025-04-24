import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import threading
import traceback
import time

from configs import *
from utils import log
from cache_handler import CacheType, get_from_cache, save_to_cache

def improved_multi_thread_download(url: str, headers: dict, file_size: int):
    try:
        cached_data = get_from_cache(CacheType.WEB_FILE, url + "#" + str(headers) + "#" + str(file_size))
        if cached_data is not None:
            return cached_data
    except Exception as e:
        log(f"获取缓存失败: {str(e)}")
        traceback.print_exc()
        raise

    old_headers = headers
    new_headers = {}
    for k, v in headers.items():
        new_headers[k.lower()] = v
    headers = new_headers

    try:
        log(f"开始多线程下载 (总大小: {file_size/1024/1024:.2f}MB)")

        # 动态任务分配参数
        chunk_size = 1024 * 512  # 每个任务0.5MB
        total_chunks = (file_size + chunk_size - 1) // chunk_size
        
        # 线程安全的缓冲区和进度条
        buffer = bytearray(file_size)
        progress_bar = tqdm(total=file_size, unit='B', unit_scale=True, desc="下载进度")
        lock = threading.Lock()
        exceptions = []
        max_retries = 3  # 最大重试次数

        def download_chunk(chunk_id):
            retries = 0
            while retries <= max_retries:
                try:
                    start = chunk_id * chunk_size
                    end = min(start + chunk_size - 1, file_size - 1)
                    headers["Range"] = f"bytes={start}-{end}"

                    session = requests.Session()
                    session.trust_env = DOWNLOADER_TRUST_ENV
                    
                    # 设置连接超时和读取超时
                    with session.get(url, headers=headers, stream=True, timeout=(5, 30), proxies=DOWNLOADER_PROXIES, allow_redirects=True) as r:
                        r.raise_for_status()
                        chunk_data = r.content
                        
                        with lock:
                            buffer[start:start+len(chunk_data)] = chunk_data
                            progress_bar.update(len(chunk_data))
                    break  # 下载成功则退出循环
                    
                except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                    retries += 1
                    if retries > max_retries:
                        with lock:
                            exceptions.append(e)
                            log(f"分片 {chunk_id} 下载失败: {str(e)}")
                            traceback.print_exc()
                        break
                    time.sleep(2 ** retries)  # 指数退避重试
                except Exception as e:
                    with lock:
                        exceptions.append(e)
                        log(f"分片 {chunk_id} 下载异常: {str(e)}")
                        traceback.print_exc()
                    break

        # 使用线程池动态分配任务
        with ThreadPoolExecutor(max_workers=DOWNLOADER_MAX_THREADS) as executor:
            futures = [executor.submit(download_chunk, i) for i in range(total_chunks)]
            
            # 实时监控任务状态
            for future in as_completed(futures):
                if exceptions:
                    executor.shutdown(wait=False)
                    raise exceptions[0]

        progress_bar.close()

        result = bytes(buffer)
        save_to_cache(CacheType.WEB_FILE, url + "#" + str(old_headers) + "#" + str(file_size), result)
        log("下载完成并已缓存")
        return result

    except Exception as e:
        log(f"下载失败: {str(e)}")
        traceback.print_exc()
        return b''