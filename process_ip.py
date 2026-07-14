import requests
import os
import json
from pathlib import Path

# 三个源链接，顺序：yongbusi 第一
URL_YONGBUSI = "https://raw.githubusercontent.com/xxsa520/cf-IP/refs/heads/main/yongbusi.txt"
URL_VPS789 = "https://vps789.com/openApi/cfIpApi"  # 新增的VPS789接口
URL_CFXYZ = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/Cfxyz.txt"
URL_SG = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/SG.txt"


OUT_DIR = Path("output")
OUT_YONGBUSI = OUT_DIR / "Yongbusi_processed.txt"
OUT_VPS789 = OUT_DIR / "VPS789_processed.txt"  # 新增的VPS789处理文件
OUT_CF = OUT_DIR / "Cfxyz_processed.txt"
OUT_SG = OUT_DIR / "SG_processed.txt"
OUT_MERGE = OUT_DIR / "all_ip.txt"

# 新增：VPS789分类输出文件
OUT_SG_MOBILE = OUT_DIR / "SG_mobile.txt"
OUT_SG_TELECOM = OUT_DIR / "SG_telecom.txt"
OUT_SG_UNICOM = OUT_DIR / "SG_unicom.txt"

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

# 新增：处理VPS789接口数据
def process_vps789(content: str) -> dict:
    """
    处理VPS789接口返回的数据，按运营商分类
    返回包含三个分类列表的字典
    """
    try:
        data = json.loads(content)
        ip_list = data.get('data', []) if isinstance(data, dict) else data
        
        classified = {
            'mobile': [],    # SG移动
            'telecom': [],   # SG电信
            'unicom': []     # SG联通
        }
        
        for item in ip_list:
            # 假设API返回格式为：{"ip": "1.1.1.1", "isp": "移动"} 或直接是IP字符串
            if isinstance(item, dict):
                ip = item.get('ip', '')
                isp = item.get('isp', '').lower()
            else:
                ip = str(item)
                isp = '未知'
            
            # 根据ISP信息分类
            if '移动' in isp or 'mobile' in isp:
                classified['mobile'].append(f"{ip}:443#SG移动")
            elif '电信' in isp or 'telecom' in isp:
                classified['telecom'].append(f"{ip}:443#SG电信")
            elif '联通' in isp or 'unicom' in isp:
                classified['unicom'].append(f"{ip}:443#SG联通")
            else:
                # 未知运营商，默认归为移动（可根据需求调整）
                classified['mobile'].append(f"{ip}:443#SG移动")
        
        return classified
    
    except json.JSONDecodeError:
        # 如果不是JSON格式，尝试按行处理
        lines = content.strip().split('\n')
        classified = {
            'mobile': [],
            'telecom': [],
            'unicom': []
        }
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#'):
                # 简单的IP格式判断（实际应用中可能需要更复杂的逻辑）
                if '.' in line and ':' not in line:
                    ip = line
                    # 这里需要根据IP段判断运营商，简化处理：全部归为移动
                    # 实际应用中应该使用IP地理位置查询服务
                    classified['mobile'].append(f"{ip}:443#SG移动")
        
        return classified

# 新增：保存分类后的VPS789数据
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

# 合并四份处理后的文本
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
        
        # 保存原始处理数据（可选）
        with open(OUT_VPS789, "w", encoding="utf-8") as f:
            json.dump(vps789_classified, f, ensure_ascii=False, indent=2)
        print(f"VPS789处理完成 → {OUT_VPS789}")
        
    except Exception as e:
        print(f"⚠️ VPS789接口处理失败: {e}")
        print("将使用空数据继续处理...")
        vps789_classified = {
            'mobile': [],
            'telecom': [],
            'unicom': []
        }

    # 读取三份文件合并
    with open(OUT_YONGBUSI, "r", encoding="utf-8") as f:
        yong_data = f.read()
    with open(OUT_CF, "r", encoding="utf-8") as f:
        cf_data = f.read()
    with open(OUT_SG, "r", encoding="utf-8") as f:
        sg_data = f.read()

    # 合并所有数据
    merge_all(yong_data, cf_data, sg_data, vps789_classified)

if __name__ == "__main__":
    main()
