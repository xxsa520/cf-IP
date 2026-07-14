import requests
import os
import json
import re
from pathlib import Path

# 四个源链接
URL_YONGBUSI = "https://raw.githubusercontent.com/xxsa520/cf-IP/refs/heads/main/yongbusi.txt"
URL_CFXYZ = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/Cfxyz.txt"
URL_SG = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/SG.txt"
URL_VPS789 = "https://vps789.com/openApi/cfIpApi"

OUT_DIR = Path("output")
OUT_YONGBUSI = OUT_DIR / "Yongbusi_processed.txt"
OUT_CF = OUT_DIR / "Cfxyz_processed.txt"
OUT_SG = OUT_DIR / "SG_processed.txt"
OUT_VPS789 = OUT_DIR / "VPS789_processed.txt"
OUT_MERGE = OUT_DIR / "all_ip.txt"

# 分类输出文件
OUT_SG_MOBILE = OUT_DIR / "SG_mobile.txt"
OUT_SG_TELECOM = OUT_DIR / "SG_telecom.txt"
OUT_SG_UNICOM = OUT_DIR / "SG_unicom.txt"

# 全局严格的IPv4正则
ip_pattern = re.compile(r'\b((?:\d{1,3}\.){3}\d{1,3})\b')

def download_raw(url: str) -> str:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text

def replace_all_speed_tag(content: str) -> str:
    return content.replace("【测速 Nodes】", "新加坡")

def process_sg(content: str) -> str:
    content = content.replace("sg 【新加坡】 SG", "新加坡")
    content = replace_all_speed_tag(content)
    return content

def extract_isp_from_key(key_str):
    """从字符串中提取运营商类型"""
    if not key_str: return None
    key_str = str(key_str).upper()
    if 'ALLAVG' in key_str or 'AVG' in key_str:
        return None
    if 'CT' in key_str or 'TELECOM' in key_str or '电信' in key_str:
        return 'telecom'
    elif 'CU' in key_str or 'UNICOM' in key_str or '联通' in key_str:
        return 'unicom'
    elif 'CM' in key_str or 'MOBILE' in key_str or '移动' in key_str:
        return 'mobile'
    return None

def clean_unwanted_lines(content: str) -> str:
    """
    全局清洗：剔除文本中不包含IP的纯标签行(如 unicom, telecom, mobile, CT, AllAvg)
    """
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        if ip_pattern.search(line):
            cleaned_lines.append(line)
            continue
            
        stripped_line = line.strip().replace(':', '').replace('#', '').replace('-', '').replace('_', '').strip()
        if not stripped_line:
            cleaned_lines.append(line)
            continue
            
        isp_type = extract_isp_from_key(stripped_line)
        if isp_type or 'ALLAVG' in stripped_line.upper() or 'AVG' in stripped_line.upper():
            continue
            
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)

def process_vps789(content: str) -> dict:
    """
    健壮解析 VPS789 接口数据。
    """
    classified = {'mobile': [], 'telecom': [], 'unicom': []}
    # 您的示例中要求格式为 "#移动"，如果想改为 "#SG移动" 可在此处修改
    isp_name_map = {'mobile': '移动', 'telecom': '电信', 'unicom': '联通'}
    
    def add_ip(ip, isp_type):
        if ip and isp_type:
            classified[isp_type].append(f"{ip}:443#{isp_name_map[isp_type]}")

    try:
        data = json.loads(content)
        
        def parse_json(obj):
            if isinstance(obj, dict):
                ip_val = None
                isp_val = None
                for k, v in obj.items():
                    k_lower = str(k).lower()
                    if k_lower in ['ip', 'address', 'host', 'addr']:
                        ips = ip_pattern.findall(str(v))
                        if ips: ip_val = ips[0]
                    else:
                        temp_isp = extract_isp_from_key(k) or extract_isp_from_key(v)
                        if temp_isp: isp_val = temp_isp
                
                if ip_val and isp_val:
                    add_ip(ip_val, isp_val)
                    return
                
                for k, v in obj.items():
                    isp_type = extract_isp_from_key(k)
                    if isp_type:
                        ips = ip_pattern.findall(str(v))
                        for ip in ips:
                            add_ip(ip, isp_type)
                    else:
                        parse_json(v)
                        
            elif isinstance(obj, list):
                for item in obj:
                    parse_json(item)
            elif isinstance(obj, str):
                isp_type = extract_isp_from_key(obj)
                if isp_type:
                    ips = ip_pattern.findall(obj)
                    for ip in ips:
                        add_ip(ip, isp_type)
                        
        parse_json(data)
        
    except json.JSONDecodeError:
        lines = content.split('\n')
        current_isp = None
        for line in lines:
            line = line.strip()
            if not line: continue
            line_isp = extract_isp_from_key(line)
            if line_isp:
                current_isp = line_isp
            ips = ip_pattern.findall(line)
            for ip in ips:
                target_isp = line_isp if line_isp else current_isp
                if target_isp:
                    add_ip(ip, target_isp)
                else:
                    add_ip(ip, 'mobile')

    # 去重
    for k in classified:
        classified[k] = list(dict.fromkeys(classified[k]))
    return classified

def save_classified_vps789(classified_data: dict):
    # 保存单独的分类文件
    with open(OUT_SG_MOBILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(classified_data['mobile']))
    with open(OUT_SG_TELECOM, 'w', encoding='utf-8') as f:
        f.write('\n'.join(classified_data['telecom']))
    with open(OUT_SG_UNICOM, 'w', encoding='utf-8') as f:
        f.write('\n'.join(classified_data['unicom']))
        
    print(f"VPS789分类数据已保存：")
    print(f"  - SG移动: {len(classified_data['mobile'])}个IP → {OUT_SG_MOBILE}")
    print(f"  - SG电信: {len(classified_data['telecom'])}个IP → {OUT_SG_TELECOM}")
    print(f"  - SG联通: {len(classified_data['unicom'])}个IP → {OUT_SG_UNICOM}")

def merge_all(yongbusi_txt, cfxyz_txt, sg_txt, vps789_classified):
    vps789_content = "\n".join([
        "\n".join(vps789_classified['mobile']),
        "\n".join(vps789_classified['telecom']),
        "\n".join(vps789_classified['unicom'])
    ])
    merge_content = f"{yongbusi_txt}\n\n{cfxyz_txt}\n\n{sg_txt}\n\n{vps789_content}"
    with open(OUT_MERGE, "w", encoding="utf-8") as f:
        f.write(merge_content)
    print(f"四合一合并完成，输出文件：{OUT_MERGE}")

def main():
    OUT_DIR.mkdir(exist_ok=True)

    # 1. yongbusi.txt
    print("1/4 正在下载处理 yongbusi.txt ...")
    yongbusi_raw = download_raw(URL_YONGBUSI)
    yongbusi_proc = replace_all_speed_tag(yongbusi_raw)
    yongbusi_proc = clean_unwanted_lines(yongbusi_proc)
    with open(OUT_YONGBUSI, "w", encoding="utf-8") as f:
        f.write(yongbusi_proc)
    print(f"yongbusi处理完成 → {OUT_YONGBUSI}")

    # 2. Cfxyz.txt
    print("2/4 正在下载处理 Cfxyz.txt ...")
    cf_raw = download_raw(URL_CFXYZ)
    cf_proc = replace_all_speed_tag(cf_raw)
    cf_proc = clean_unwanted_lines(cf_proc)
    with open(OUT_CF, "w", encoding="utf-8") as f:
        f.write(cf_proc)
    print(f"Cfxyz处理完成 → {OUT_CF}")

    # 3. SG.txt
    print("3/4 正在下载处理 SG.txt ...")
    sg_raw = download_raw(URL_SG)
    sg_proc = process_sg(sg_raw)
    sg_proc = clean_unwanted_lines(sg_proc)
    with open(OUT_SG, "w", encoding="utf-8") as f:
        f.write(sg_proc)
    print(f"SG处理完成 → {OUT_SG}")

    # 4. VPS789 接口
    print("4/4 正在下载处理 VPS789接口数据 ...")
    try:
        vps789_raw = download_raw(URL_VPS789)
        vps789_classified = process_vps789(vps789_raw)
        save_classified_vps789(vps789_classified)
        
        # 【修改点】以纯文本格式保存合并后的VPS789数据，一行一个IP
        with open(OUT_VPS789, "w", encoding="utf-8") as f:
            all_vps789_ips = vps789_classified['mobile'] + vps789_classified['telecom'] + vps789_classified['unicom']
            f.write("\n".join(all_vps789_ips))
            
        print(f"VPS789处理完成 → {OUT_VPS789}")
    except Exception as e:
        print(f"⚠️ VPS789接口处理失败: {e}")
        vps789_classified = {'mobile': [], 'telecom': [], 'unicom': []}

    with open(OUT_YONGBUSI, "r", encoding="utf-8") as f: yong_data = f.read()
    with open(OUT_CF, "r", encoding="utf-8") as f: cf_data = f.read()
    with open(OUT_SG, "r", encoding="utf-8") as f: sg_data = f.read()

    merge_all(yong_data, cf_data, sg_data, vps789_classified)

if __name__ == "__main__":
    main()
