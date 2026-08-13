import requests
import time
import os

RAW_URL = "https://raw.githubusercontent.com/xxsa520/cf-IP/main/output/all_ip.txt"
TXT_CACHE_FILE = ".last_content.cache"
OUTPUT_CSV = "all_ip.csv"

def get_remote_txt():
    resp = requests.get(RAW_URL, timeout=30)
    resp.raise_for_status()
    return resp.text

def read_last_cache():
    if os.path.exists(TXT_CACHE_FILE):
        with open(TXT_CACHE_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return None

def save_cache(content):
    with open(TXT_CACHE_FILE, "w", encoding="utf-8") as f:
        f.write(content)

def generate_csv(text):
    # 简单单列csv，如果需要表头可以第一行写"ip_address"
    lines = text.splitlines()
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        f.write("ip_address\n")
        for line in lines:
            stripped = line.strip()
            if stripped:
                f.write(f"{stripped}\n")
    print(f"✅已生成 {OUTPUT_CSV}")

def main():
    interval = 60  # 轮询间隔，单位秒
    print(f"开始监控 {RAW_URL}，每{interval}秒检查一次")
    while True:
        try:
            remote_text = get_remote_txt()
            old_text = read_last_cache()
            if remote_text != old_text:
                print("🔍检测到文件内容发生变更！")
                generate_csv(remote_text)
                save_cache(remote_text)
            else:
                pass
        except Exception as e:
            print(f"❌异常：{e}")
        time.sleep(interval)

if __name__ == "__main__":
    main()
