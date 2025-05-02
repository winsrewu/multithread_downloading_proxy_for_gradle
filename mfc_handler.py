import ctypes
import os
from pathlib import Path
import socket
import traceback
import requests
import yaml

from utils import logger
from configs import *

mfc_config = {}

if os.path.exists(MFC_CONFIG_FILE):
    with open(MFC_CONFIG_FILE, "rb") as f:
        try:
            mfc_config = yaml.load(f, Loader=yaml.FullLoader)
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse {MFC_CONFIG_FILE}: {e}")

def check_mfc_config() -> bool:
    if not isinstance(mfc_config, list):
        logger.error(f"{MFC_CONFIG_FILE} should be a list")
        return False
    
    for item in mfc_config:
        if not isinstance(item, dict):
            logger.error(f"Each item in {MFC_CONFIG_FILE} should be a dictionary")
            return False
        
        if "url" not in item:
            logger.error(f"Each item in {MFC_CONFIG_FILE} should have a 'url' key")
            return False
        
        if "cache" not in item:
            logger.error(f"Each item in {MFC_CONFIG_FILE} should have a 'cache' key")
            return False
        
        if "cache" != "true" and (not os.path.exists(item["cache"]) or os.path.isdir(item["cache"])):
            logger.error(f"Cache directory {item['cache']} does not exist or is a directory")
            return False
        
    return True

if not check_mfc_config():
    raise Exception("MFC config file is invalid")

def is_cache_disabled(url: str) -> bool:
    for item in mfc_config:
        if item["url"] == url:
            return item["cache"] == "false"
    return False

def get_mfc_dir(url: str) -> Path | None:
    for item in mfc_config:
        if item["url"] == url:
            if os.path.exists(item["cache"]) and not os.path.isdir(item["cache"]):
                return Path(item["cache"])
    return None

def handle_mfc_download(client_socket: socket.socket, target_url: str, headers: dict, content_length: int, response_headers: dict, response: requests.Response, range: str | None, full_length: int | None):
    mfc_path = get_mfc_dir(target_url)
    if mfc_path is None:
        raise Exception("MFC cache directory not found, should not happen due to previous check")
    
    if mfc_path.stat().st_size != full_length:
        logger.error(f"MFC cache file size {os.path.getsize(mfc_path)} does not match full length {full_length}")
        return
    
    l_range = 0
    r_range = None
    if range is not None:
        _range = range.split("=")[1]
        l_range = int(_range.split("-")[0])
        if len(_range.split("-")) == 2 and _range.split("-")[1] != "":
            r_range = int(_range.split("-")[1])

    try:
        def safe_send(data):
            try:
                client_socket.sendall(data)
                return True
            except (ConnectionResetError, BrokenPipeError, socket.timeout) as e:
                logger.error(f"Send failed: {type(e).__name__}")
                return False
            
        if not range or not r_range:
            r_range = l_range + content_length - 1
        
        if range is not None:
            response_headers["Content-Range"] = f"bytes {l_range}-{r_range}/{full_length}"
            response_headers["Accept-Ranges"] = "bytes"
        response_headers["Connection"] = "keep-alive"
        response_headers_raw = f"HTTP/1.1 {response.status_code} {response.reason}\r\n"
        for key, value in response_headers.items():
            response_headers_raw += f"{key}: {value}\r\n"
        response_headers_raw += "\r\n"

        safe_send(response_headers_raw.encode())
        
        client_socket.sendfile(mfc_path.open("rb"), l_range, r_range - l_range + 1)

        safe_send(b"\r\n")

    except Exception as e:
        logger.error(f"MFC send failed: {e}")
        logger.log(traceback.format_exc())