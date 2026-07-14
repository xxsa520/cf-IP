import requests
import re
import os
from pathlib import Path

# 配置地址
URL_CFXYZ = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/Cfxyz.txt"
URL_SG = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/SG.txt"
OUT_DIR = Path("output")
OUT_CF = OUT_DIR / "Cfxyz_processed.txt"
OUT_SG = OUT_DIR / "SG_processed.txt"

# IP缓存，减少重复请求
ip_country_cache = {}
# IPv4正则
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

def get_ip_country_cn(ip: str) -> str:
    """查询IP对应中文国家，失败返回未知"""
    if ip in ip_country_cache:
        return ip_country_cache[ip]
    try:
        resp = requests.get(f"http://ip-api.com/json/{ip}?lang=zh-CN", timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") == "success":
            country = data.get("country", "未知")
            ip_country_cache[ip] = country
            return country
        else:
            ip_country_cache[ip] = "未知"
            return "未知"
    except Exception as e:
        print(f"查询IP {ip} 失败: {str(e)}")
        ip_country_cache[ip] = "未知"
        return "未知"

def download_raw(url: str) -> str:
    """下载raw文本内容"""
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text

def process_cfxyz(content: str) -> str:
    """处理Cfxyz.txt：替换【测速 Nodes】为IP归属国家"""
    lines = content.splitlines()
    new_lines = []
    for line in lines:
        ip_match = IP_PATTERN.search(line)
        if ip_match:
            ip_addr = ip_match.group(0)
            country = get_ip_country_cn(ip_addr)
            line = line.replace("【测速 Nodes】", country)
        new_lines.append(line)
    return "\n".join(new_lines)

def process_sg(content: str) -> str:
    """处理SG.txt：sg 【新加坡】 SG → 新加坡"""
    return content.replace("sg 【新加坡】 SG", "新加坡")

def main():
    # 创建输出文件夹
    OUT_DIR.mkdir(exist_ok=True)

    # 处理Cfxyz
    print("正在下载并处理 Cfxyz.txt ...")
    cf_raw = download_raw(URL_CFXYZ)
    cf_processed = process_cfxyz(cf_raw)
    with open(OUT_CF, "w", encoding="utf-8") as f:
        f.write(cf_processed)
    print(f"Cfxyz处理完成，输出: {OUT_CF}")

    # 处理SG
    print("正在下载并处理 SG.txt ...")
    sg_raw = download_raw(URL_SG)
    sg_processed = process_sg(sg_raw)
    with open(OUT_SG, "w", encoding="utf-8") as f:
        f.write(sg_processed)
    print(f"SG处理完成，输出: {OUT_SG}")

if __name__ == "__main__":
    main()
