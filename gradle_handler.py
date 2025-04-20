import os

from utils import log
from configs import *

def set_gradle_proxies(gradle_properties_path):
    """
    修改 Gradle 的 gradle.properties 文件以设置代理和信任证书。
    :param gradle_properties_path: gradle.properties 文件的路径
    """
    # 定义需要写入的代理配置
    proxy_config = {
        "systemProp.http.proxyHost": PROXY_HOST,
        "systemProp.http.proxyPort": PROXY_PORT,
        "systemProp.https.proxyHost": PROXY_HOST,
        "systemProp.https.proxyPort": PROXY_PORT,
        "systemProp.javax.net.ssl.trustStore": os.path.abspath("truststore.jks").replace("\\", "/"),  # 信任存储文件路径
        "systemProp.javax.net.ssl.trustStorePassword": "changeit",  # 信任存储密码
        "systemProp.javax.net.ssl.trustStoreType": "JKS",  # 信任存储类型
    }

    # 读取现有内容并准备更新
    updated_lines = []
    if os.path.exists(gradle_properties_path):
        with open(gradle_properties_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        # 遍历现有行，更新或保留非代理相关的配置
        for line in lines:
            key = line.split("=")[0].strip()
            if key in proxy_config:
                # 如果已存在相关配置，则用新值覆盖
                updated_lines.append(f"{key}={proxy_config[key]}\n")
                del proxy_config[key]  # 移除已处理的配置项
            else:
                # 保留其他配置
                updated_lines.append(line)
    
    # 添加未写入的新代理配置
    for key, value in proxy_config.items():
        updated_lines.append(f"{key}={value}\n")

    # 将更新后的内容写回文件
    with open(gradle_properties_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    log(f"Gradle proxies and truststore set in {gradle_properties_path}")

def clear_gradle_proxies(gradle_properties_path):
    """
    清除 Gradle 的代理和信任证书配置。
    :param gradle_properties_path: gradle.properties 文件的路径
    """
    proxy_config = {
        "systemProp.http.proxyHost",
        "systemProp.http.proxyPort",
        "systemProp.https.proxyHost",
        "systemProp.https.proxyPort",
        "systemProp.javax.net.ssl.trustStore",
        "systemProp.javax.net.ssl.trustStorePassword",
        "systemProp.javax.net.ssl.trustStoreType",
    }

    # 读取现有内容并准备更新
    updated_lines = []
    if os.path.exists(gradle_properties_path):
        with open(gradle_properties_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        for line in lines:
            key = line.split("=")[0].strip()
            if key in proxy_config:
                # 移除相关配置
                continue
            else:
                # 保留其他配置
                updated_lines.append(line)
    
    # 将更新后的内容写回文件
    with open(gradle_properties_path, "w", encoding="utf-8") as f:
        f.writelines(updated_lines)

    log(f"Gradle proxies and truststore cleared in {gradle_properties_path}")