import requests
import os
from pathlib import Path

# 三个源链接，顺序：yongbusi 第一
URL_YONGBUSI = "https://raw.githubusercontent.com/xxsa520/cf-IP/refs/heads/main/yongbusi.txt"
URL_CFXYZ = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/Cfxyz.txt"
URL_SG = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/SG.txt"

OUT_DIR = Path("output")
OUT_YONGBUSI = OUT_DIR / "Yongbusi_processed.txt"
OUT_CF = OUT_DIR / "Cfxyz_processed.txt"
OUT_SG = OUT_DIR / "SG_processed.txt"
OUT_MERGE = OUT_DIR / "all_ip.txt"

def download_raw(url: str) -> str:
    """下载远程文本"""
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text

# 通用替换：所有【测速 Nodes】直接替换为 新加坡，无需查IP
def replace_all_speed_tag(content: str) -> str:
    return content.replace("【测速 Nodes】", "新加坡")

# SG文件专属处理
def process_sg(content: str) -> str:
    # 先替换固定字符串
    content = content.replace("sg 【新加坡】 SG", "新加坡")
    # 再统一替换测速标记
    content = replace_all_speed_tag(content)
    return content

# 合并三份处理后的文本
def merge_all(yongbusi_txt, cfxyz_txt, sg_txt):
    merge_content = f"{yongbusi_txt}\n\n{cfxyz_txt}\n\n{sg_txt}"
    with open(OUT_MERGE, "w", encoding="utf-8") as f:
        f.write(merge_content)
    print(f"三合一合并完成，输出文件：{OUT_MERGE}")

def main():
    OUT_DIR.mkdir(exist_ok=True)

    # 1. 处理 yongbusi.txt
    print("1/3 正在下载处理 yongbusi.txt ...")
    yongbusi_raw = download_raw(URL_YONGBUSI)
    yongbusi_proc = replace_all_speed_tag(yongbusi_raw)
    with open(OUT_YONGBUSI, "w", encoding="utf-8") as f:
        f.write(yongbusi_proc)
    print(f"yongbusi处理完成 → {OUT_YONGBUSI}")

    # 2. 处理 Cfxyz.txt
    print("2/3 正在下载处理 Cfxyz.txt ...")
    cf_raw = download_raw(URL_CFXYZ)
    cf_proc = replace_all_speed_tag(cf_raw)
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

    # 读取三份文件合并
    with open(OUT_YONGBUSI, "r", encoding="utf-8") as f:
        yong_data = f.read()
    with open(OUT_CF, "r", encoding="utf-8") as f:
        cf_data = f.read()
    with open(OUT_SG, "r", encoding="utf-8") as f:
        sg_data = f.read()

    merge_all(yong_data, cf_data, sg_data)

if __name__ == "__main__":
    main()
