import requests
import os
import json
import re
from pathlib import Path

# 三个源链接，顺序：yongbusi 第一
URL_YONGBUSI = "https://raw.githubusercontent.com/xxsa520/cf-IP/refs/heads/main/yongbusi.txt"
URL_CFXYZ = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/Cfxyz.txt"
URL_SG = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/SG.txt"
URL_VPS789 = "https://vps789.com/openApi/cfIpApi"  # 新增的VPS789接口

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

def download_raw(url: str) -> str:
    """下载远程文本"""
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.text

def replace_all_speed_tag(content: str) -> str:
    return content.replace("【测速 Nodes】", "新加坡")

def process_sg(content: str) -> str:
    content = content.replace("sg 【新加坡】 SG", "新加坡")
    content = replace_all_speed_tag(content)
    return content

def process_vps789(content: str) -> dict:
    """
    健壮解析 VPS789 接口数据。
    支持JSON或纯文本，通过识别 CT/CU/CM/电信/联通/移动 等关键字，
    结合IP正则提取，准确分类，避免将标签(如"CT")误判为IP。
    """
    classified = {'mobile': [], 'telecom': [], 'unicom': []}
    # 严格的IPv4正则表达式，只提取类似 1.1.1.1 的字符串，防止把 CT 当成IP
    ip_pattern = re.compile(r'\b((?:\d{1,3}\.){3}\d{1,3})\b')
    
    # 运营商名称映射辅助
    isp_name_map = {
        'mobile': '移动',
        'telecom': '电信',
        'unicom': '联通'
    }
    
    def extract_isp_from_key(key_str):
        key_str = str(key_str).upper()
        # 排除 ALLAVG，防止平均延迟的IP被误分类
        if 'ALLAVG' in key_str or 'AVG' in key_str:
            return None
        if 'CT' in key_str or 'TELECOM' in key_str or '电信' in key_str:
            return 'telecom'
        elif 'CU' in key_str or 'UNICOM' in key_str or '联通' in key_str:
            return 'unicom'
        elif 'CM' in key_str or 'MOBILE' in key_str or '移动' in key_str:
            return 'mobile'
        return None
        
    def add_ip(ip, isp_type):
        if ip and isp_type:
            classified[isp_type].append(f"{ip}:443#{isp_name_map[isp_type]}")

    try:
        # 尝试按 JSON 解析
        data = json.loads(content)
        
        def parse_json(obj):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    isp_type = extract_isp_from_key(k)
                    # 如果当前键是运营商类型(如CT/CU/CM)，提取值中的IP
                    if isp_type:
                        ips = ip_pattern.findall(str(v))
                        for ip in ips:
                            add_ip(ip, isp_type)
                    else:
                        # 键不是运营商标识，继续递归遍历值
                        parse_json(v)
            elif isinstance(obj, list):
                for item in obj:
                    parse_json(item)
            elif isinstance(obj, str):
                # 如果字符串本身带有运营商标识，提取IP
                isp_type = extract_isp_from_key(obj)
                if isp_type:
                    ips = ip_pattern.findall(obj)
                    for ip in ips:
                        add_ip(ip, isp_type)
                        
        parse_json(data)
        
    except json.JSONDecodeError:
        # 如果不是JSON格式，按纯文本逐行处理
        lines = content.split('\n')
        current_isp = None
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 检查当前行是否包含运营商标识
            line_isp = extract_isp_from_key(line)
            if line_isp:
                current_isp = line_isp
                
            # 严格提取当前行的所有真实IP
            ips = ip_pattern.findall(line)
            for ip in ips:
                # 优先使用当前行识别到的运营商，其次使用上文记忆的运营商
                target_isp = line_isp if line_isp else current_isp
                if target_isp:
                    add_ip(ip, target_isp)
                else:
                    # 如果都没有识别到，可按需处理，这里默认归为移动
                    add_ip(ip, 'mobile')

    # 对列表去重，保持原有顺序
    for k in classified:
        classified[k] = list(dict.fromkeys(classified[k]))
        
    return classified

def save_classified_vps789(classified_data: dict):
    """保存分类后的VPS789数据到单独文件"""
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
    # 合并VPS789分类数据
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

    # 1. 处理 yongbusi.txt
    print("1/4 正在下载处理 yongbusi.txt ...")
    yongbusi_raw = download_raw(URL_YONGBUSI)
    yongbusi_proc = replace_all_speed_tag(yongbusi_raw)
    with open(OUT_YONGBUSI, "w", encoding="utf-8") as f:
        f.write(yongbusi_proc)
    print(f"yongbusi处理完成 → {OUT_YONGBUSI}")

    # 2. 处理 Cfxyz.txt
    print("2/4 正在下载处理 Cfxyz.txt ...")
    cf_raw = download_raw(URL_CFXYZ)
    cf_proc = replace_all_speed_tag(cf_raw)
    with open(OUT_CF, "w", encoding="utf-8") as f:
        f.write(cf_proc)
    print(f"Cfxyz处理完成 → {OUT_CF}")

    # 3. 处理 SG.txt
    print("3/4 正在下载处理 SG.txt ...")
    sg_raw = download_raw(URL_SG)
    sg_proc = process_sg(sg_raw)
    with open(OUT_SG, "w", encoding="utf-8") as f:
        f.write(sg_proc)
    print(f"SG处理完成 → {OUT_SG}")

    # 4. 处理 VPS789 接口
    print("4/4 正在下载处理 VPS789接口数据 ...")
    try:
        vps789_raw = download_raw(URL_VPS789)
        vps789_classified = process_vps789(vps789_raw)
        
        # 保存分类数据
        save_classified_vps789(vps789_classified)
        
        # 保存原始处理数据用于检查
        with open(OUT_VPS789, "w", encoding="utf-8") as f:
            json.dump(vps789_classified, f, ensure_ascii=False, indent=2)
        print(f"VPS789处理完成 → {OUT_VPS789}")
        
    except Exception as e:
        print(f"⚠️ VPS789接口处理失败: {e}")
        vps789_classified = {'mobile': [], 'telecom': [], 'unicom': []}

    # 读取文件合并
    with open(OUT_YONGBUSI, "r", encoding="utf-8") as f:
        yong_data = f.read()
    with open(OUT_CF, "r", encoding="utf-8") as f:
        cf_data = f.read()
    with open(OUT_SG, "r", encoding="utf-8") as f:
        sg_data = f.read()

    merge_all(yong_data, cf_data, sg_data, vps789_classified)

if __name__ == "__main__":
    main()
