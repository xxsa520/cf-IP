import requests
import re
import os
from pathlib import Path

# 配置地址（新增yongbusi放在首位）
URL_YONGBUSI = "https://raw.githubusercontent.com/xxsa520/cf-IP/refs/heads/main/yongbusi.txt"
URL_CFXYZ = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/Cfxyz.txt"
URL_SG = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/SG.txt"

OUT_DIR = Path("output")
OUT_YONGBUSI = OUT_DIR / "Yongbusi_processed.txt"
OUT_CF = OUT_DIR / "Cfxyz_processed.txt"
OUT_SG = OUT_DIR / "SG_processed.txt"
OUT_MERGE = OUT_DIR / "all_ip.txt"

# IP查询缓存
ip_country_cache = {}
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

def get_ip_country_cn(ip: str) -> str:
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
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text

# 通用处理：替换【测速 Nodes】为国家（yongbusi、cfxyz共用）
def replace_speed_tag(content: str) -> str:
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

# SG专用替换规则
def process_sg(content: str) -> str:
    return content.replace("sg 【新加坡】 SG", "新加坡")

# 合并三份文件
def merge_all(yongbusi_txt, cfxyz_txt, sg_txt):
    # 三段内容用空行分隔
    merge_content = f"{yongbusi_txt}\n\n{cfxyz_txt}\n\n{sg_txt}"
    with open(OUT_MERGE, "w", encoding="utf-8") as f:
        f.write(merge_content)
    print(f"三合一合并完成，输出文件：{OUT_MERGE}")

def main():
    OUT_DIR.mkdir(exist_ok=True)

    # 1. 优先处理 yongbusi.txt
    print("1/3 正在下载处理 yongbusi.txt ...")
    yongbusi_raw = download_raw(URL_YONGBUSI)
    yongbusi_proc = replace_speed_tag(yongbusi_raw)
    with open(OUT_YONGBUSI, "w", encoding="utf-8") as f:
        f.write(yongbusi_proc)
    print(f"yongbusi处理完成 → {OUT_YONGBUSI}")

    # 2. 处理 Cfxyz.txt
    print("2/3 正在下载处理 Cfxyz.txt ...")
    cf_raw = download_raw(URL_CFXYZ)
    cf_proc = replace_speed_tag(cf_raw)
    with open(OUT_CF, "w", encoding="utf-8") as f:
        f.write(cf_proc)
    print(f"Cfxyz处理完成 → {OUT_CF}")

    # 3. 处理 SG.txt
    print("3/3 正在下载处理 SG.txt ...")
    sg_raw = download_raw(URL_SG)
    sg_proc = process_sg(sg_raw)
    with open(OUT_SG, "w", encoding="utf-8") as f:
        f.write(sg_proc)
    print(f"SG处理完成 → {OUT_SG}")

    # 读取三份处理后内容合并
    with open(OUT_YONGBUSI, "r", encoding="utf-8") as f:
        yong_data = f.read()
    with open(OUT_CF, "r", encoding="utf-8") as f:
        cf_data = f.read()
    with open(OUT_SG, "r", encoding="utf-8") as f:
        sg_data = f.read()

    merge_all(yong_data, cf_data, sg_data)

if __name__ == "__main__":
    main()
