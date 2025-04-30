import multiprocessing
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import traceback
import time

import urllib3

from configs import *
from utils import log, progress_bar, logger
from cache_handler import CacheType, get_from_cache, save_to_cache

def generate_schedule(l_range: int, r_range: int):
    file_size = r_range - l_range + 1
    # decide the chunk size based on the file size
    if file_size <= 10 * 1024 * 1024:  # 10MB
        chunk_size = file_size // DOWNLOADER_MAX_THREADS
    elif file_size <= 500 * 1024 * 1024:  # 500MB
        chunk_size = file_size // DOWNLOADER_MAX_THREADS // 3
    else:
        chunk_size = DOWNLOADER_MAX_CHUNK_SIZE

    if chunk_size > DOWNLOADER_MAX_CHUNK_SIZE:
        chunk_size = DOWNLOADER_MAX_CHUNK_SIZE

    schedule = []

    # generate the schedule
    total_chunks = (file_size + chunk_size - 1) // chunk_size
    for i in range(total_chunks):
        start = i * chunk_size
        end = min(start + chunk_size - 1, file_size - 1)
        schedule.append({
            "start": start + l_range,
            "end": end + l_range,
            "chunk_id": i,
            "chunk_data": None,
            "consumed": False,
            "downloaded": False,
        })

    return schedule

def download_file_with_schedule(url: str, headers: dict, file_size: int, schedule: list, lock: threading.Lock):
    """下载文件, 如果击中缓存就返回bytes形式, 否则通过callback实时更新下载进度"""
    try:
        cached_data = get_from_cache(CacheType.WEB_FILE, url + "#" + str(headers) + "#" + str(file_size))
        if cached_data is not None:
            return cached_data
    except Exception as e:
        logger.error(f"获取缓存失败: {str(e)}")
        traceback.print_exc()
        raise

    old_headers = headers
    new_headers = {}
    for k, v in headers.items():
        new_headers[k] = v
    headers = new_headers

    progress_task = progress_bar.create_task(f"downloading {url}", total=file_size)

    try:
        log(f"开始多线程下载 (总大小: {file_size/1024/1024:.2f}MB)")
        
        exceptions = []
        max_retries = 3  # 最大重试次数

        def download_chunk(schedule_item: dict, on_success_callback: callable):
            retries = 0
            while retries <= max_retries:
                try:
                    start = schedule_item["start"]
                    end = schedule_item["end"]
                    headers["Range"] = f"bytes={start}-{end}"

                    session = requests.Session()
                    session.trust_env = DOWNLOADER_TRUST_ENV

                    # http = urllib3.PoolManager()
                    
                    # 设置连接超时和读取超时
                    with session.get(url, headers=headers, stream=False, timeout=(5, 30), proxies=DOWNLOADER_PROXIES, allow_redirects=False) as r:
                    # with http.request('GET', url, headers=headers, preload_content=False, timeout=urllib3.Timeout(connect=5, read=30), retries=urllib3.Retry(total=3)) as r:
                        # r.decode_content = False
                        if r.status_code >= 300 or r.status_code < 200:
                            raise requests.exceptions.HTTPError(f"HTTP {r.status_code} {r.reason}")
                        chunk_data = r.content

                        if len(chunk_data) != (end - start + 1):
                            raise Exception(f"分片大小不匹配: {len(chunk_data)}!= {(end - start + 1)} for {schedule_item['chunk_id']}")

                        # log(f"response headers: {r.headers}") #!TEST
                        
                        with lock:
                            schedule_item["chunk_data"] = chunk_data
                            schedule_item["downloaded"] = True
                            progress_bar.update(progress_task, len(chunk_data))
                            on_success_callback()

                    break  # 下载成功则退出循环
                    
                except Exception as e:
                    retries += 1
                    if retries > max_retries:
                        with lock:
                            exceptions.append(e)
                            logger.error(f"分片 {schedule_item['chunk_id']} 下载失败: {str(e)}")
                            traceback.print_exc()
                        break
                    time.sleep(2 ** retries)  # 指数退避重试

        # 使用线程池动态分配任务
        with ThreadPoolExecutor(max_workers=DOWNLOADER_MAX_THREADS) as executor:
            def on_success_callback():
                pass

            futures = [executor.submit(download_chunk, schedule_item, on_success_callback) for schedule_item in schedule]
            
            # 实时监控任务状态
            for future in as_completed(futures):
                if exceptions:
                    executor.shutdown(wait=False)
                    raise exceptions[0]

        

        result = b''.join([schedule_item["chunk_data"] for schedule_item in schedule if schedule_item["chunk_data"] is not None])
        save_to_cache(CacheType.WEB_FILE, url + "#" + str(old_headers) + "#" + str(file_size), result)
        log("下载完成并已缓存")
        return

    except Exception as e:
        logger.error(f"下载失败: {str(e)}")
        traceback.print_exc()
    finally:
        progress_bar.remove_task(progress_task)