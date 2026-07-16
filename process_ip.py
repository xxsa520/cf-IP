import requests
import os
import json
import re
from pathlib import Path
from bs4 import BeautifulSoup  # 需要安装: pip install beautifulsoup4

# ==================== 配置区 ====================
# 原有源链接
URL_YONGBUSI = "https://raw.githubusercontent.com/xxsa520/cf-IP/refs/heads/main/yongbusi.txt"
URL_CFXYZ = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/Cfxyz.txt"
URL_SG = "https://raw.githubusercontent.com/gslege/CloudflareIP/refs/heads/main/SG.txt"

# 新增的三个运营商源链接
URL_CT = "https://cf.090227.xyz/ct?ips=6"    # 电信
URL_CU = "https://cf.090227.xyz/cu"          # 联通
URL_CMCC = "https://cf.090227.xyz/cmcc?ips=8" # 移动

# 网页数据源
URL_WEB_IP = "https://ip.164746.xyz/"

# 输出目录
OUT_DIR = Path("output")
OUT_YONGBUSI = OUT_DIR / "Yongbusi_processed.txt"
OUT_CF = OUT_DIR / "Cfxyz_processed.txt"
OUT_SG = OUT_DIR / "SG_processed.txt"

# 新增运营商分类输出文件
OUT_CT = OUT_DIR / "CT_telecom.txt"        # 电信
OUT_CU = OUT_DIR / "CU_unicom.txt"        # 联通
OUT_CMCC = OUT_DIR / "CMCC_mobile.txt"    # 移动
OUT_WEB_IP = OUT_DIR / "Web_fast_ip.txt"  # 网页高速IP

# 合并输出文件
OUT_MERGE = OUT_DIR / "all_ip.txt"

# 全局严格的IPv4正则
ip_pattern = re.compile(r'\b((?:\d{1,3}\.){3}\d{1,3})\b')

# ==================== 工具函数 ====================
def download_raw(url: str) -> str:
    """下载原始文本内容"""
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        print(f"⚠️ 下载失败 {url}: {e}")
        return ""

def replace_all_speed_tag(content: str) -> str:
    """替换测速标签"""
    return content.replace("【测速 Nodes】", "新加坡")

def process_sg(content: str) -> str:
    """处理SG特定格式"""
    content = content.replace("sg 【新加坡】 SG", "新加坡")
    content = replace_all_speed_tag(content)
    return content

def extract_isp_from_key(key_str):
    """从字符串中提取运营商类型"""
    if not key_str: 
        return None
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
    全局清洗：剔除纯标签行(如 unicom, telecom, CT, AllAvg)
    但保留包含域名或其他有效节点信息的行
    """
    lines = content.split('\n')
    cleaned_lines = []
    for line in lines:
        # 1. 包含IP的行直接保留
        if ip_pattern.search(line):
            cleaned_lines.append(line)
            continue
            
        stripped_line = line.strip().replace(':', '').replace('#', '').replace('-', '').replace('_', '').replace(' ', '')
        if not stripped_line:
            cleaned_lines.append(line) # 保留空行维持格式
            continue
            
        # 2. 检查是否含有运营商标签
        isp_type = extract_isp_from_key(stripped_line)
        if isp_type or 'ALLAVG' in stripped_line.upper() or 'AVG' in stripped_line.upper():
            # 进一步判断：去掉所有可能的运营商标识后，是否还有其他字符
            test_str = stripped_line.upper()
            test_str = test_str.replace('TELECOM', '').replace('UNICOM', '').replace('MOBILE', '')
            test_str = test_str.replace('CT', '').replace('CU', '').replace('CM', '')
            test_str = test_str.replace('电信', '').replace('联通', '').replace('移动', '')
            test_str = test_str.replace('SG', '').replace('ALLAVG', '').replace('AVG', '')
            
            # 如果去掉这些标识后什么都没剩下，说明是纯标签行(如 "mobile", "CT: ", "SG移动")，丢弃
            if not test_str:
                continue
            # 如果还有剩余(如 "www5hcom443" )，说明是有效节点，保留
            cleaned_lines.append(line)
            continue
            
        # 3. 其他普通行直接保留
        cleaned_lines.append(line)
        
    return '\n'.join(cleaned_lines)

# ==================== 新增功能函数 ====================
def process_operator_url(url: str, isp_type: str) -> list:
    """
    处理运营商URL，返回IP列表
    :param url: 运营商API URL
    :param isp_type: 运营商类型
    :return: IP列表
    """
    print(f"正在下载处理 {isp_type} 运营商IP...")
    content = download_raw(url)
    if not content:
        return []
    
    # 提取所有IP
    ips = ip_pattern.findall(content)
    
    # 去重并保持顺序
    seen = set()
    unique_ips = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip)
            unique_ips.append(ip)
    
    print(f"  {isp_type}: 提取到 {len(unique_ips)} 个唯一IP")
    return unique_ips

def extract_fast_ips_from_web(url: str, min_speed: float = 50.0) -> list:
    """
    从网页提取下载速度大于指定阈值的IP
    :param url: 网页URL
    :param min_speed: 最小下载速度
    :return: 符合条件的IP列表
    """
    print(f"正在从网页提取高速IP (速度 > {min_speed}MB/s)...")
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        html_content = resp.text
        
        # 使用BeautifulSoup解析HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 查找表格 - 网页使用Markdown表格格式
        # 先尝试查找table标签，如果没有则查找pre标签中的文本
        table = soup.find('table')
        if table:
            # 如果是HTML表格
            rows = table.find_all('tr')
            fast_ips = []
            for row in rows[1:]:  # 跳过表头
                cols = row.find_all('td')
                if len(cols) >= 6:
                    ip_text = cols[0].get_text(strip=True)
                    speed_text = cols[5].get_text(strip=True)
                    
                    # 提取IP地址
                    ip_match = ip_pattern.search(ip_text)
                    if ip_match:
                        ip = ip_match.group(1)
                        
                        # 提取速度数值
                        speed_match = re.search(r'(\d+\.?\d*)\s*MB/s', speed_text, re.IGNORECASE)
                        if speed_match:
                            speed = float(speed_match.group(1))
                            if speed >= min_speed:
                                fast_ips.append({
                                    'ip': ip,
                                    'speed': speed,
                                    'latency': cols[4].get_text(strip=True) if len(cols) > 4 else "N/A"
                                })
        else:
            # 如果是Markdown表格文本（在pre或code标签中）
            pre_tag = soup.find('pre') or soup.find('code')
            if pre_tag:
                text = pre_tag.get_text()
                lines = text.split('\n')
                fast_ips = []
                for line in lines:
                    if '|' in line and 'IP地址' not in line and '---' not in line:
                        parts = [p.strip() for p in line.split('|')]
                        if len(parts) >= 7:
                            ip_text = parts[1]
                            speed_text = parts[6]
                            
                            # 提取IP地址
                            ip_match = ip_pattern.search(ip_text)
                            if ip_match:
                                ip = ip_match.group(1)
                                
                                # 提取速度数值
                                speed_match = re.search(r'(\d+\.?\d*)\s*MB/s', speed_text, re.IGNORECASE)
                                if speed_match:
                                    speed = float(speed_match.group(1))
                                    if speed >= min_speed:
                                        fast_ips.append({
                                            'ip': ip,
                                            'speed': speed,
                                            'latency': parts[5] if len(parts) > 5 else "N/A"
                                        })
            else:
                # 直接解析整个文本
                fast_ips = []
                lines = html_content.split('\n')
                for line in lines:
                    if '|' in line and 'IP地址' not in line and '---' not in line:
                        parts = [p.strip() for p in line.split('|')]
                        if len(parts) >= 7:
                            ip_text = parts[1]
                            speed_text = parts[6]
                            
                            # 提取IP地址
                            ip_match = ip_pattern.search(ip_text)
                            if ip_match:
                                ip = ip_match.group(1)
                                
                                # 提取速度数值
                                speed_match = re.search(r'(\d+\.?\d*)\s*MB/s', speed_text, re.IGNORECASE)
                                if speed_match:
                                    speed = float(speed_match.group(1))
                                    if speed >= min_speed:
                                        fast_ips.append({
                                            'ip': ip,
                                            'speed': speed,
                                            'latency': parts[5] if len(parts) > 5 else "N/A"
                                        })
        
        # 按速度降序排序
        fast_ips.sort(key=lambda x: x['speed'], reverse=True)
        
        print(f"  网页高速IP: 找到 {len(fast_ips)} 个IP (速度 > {min_speed}MB/s)")
        return fast_ips
        
    except Exception as e:
        print(f"⚠️ 网页数据提取失败: {e}")
        return []

def save_operator_ips(ips: list, filepath: Path, isp_name: str):
    """保存运营商IP到文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for ip in ips:
            f.write(f"{ip}\n")
    print(f"  {isp_name} IP已保存: {len(ips)}个 → {filepath}")

def save_web_fast_ips(fast_ips: list, filepath: Path):
    """保存网页高速IP到文件"""
    with open(filepath, 'w', encoding='utf-8') as f:
        for item in fast_ips:
            f.write(f"{item['ip']}#{item['speed']:.2f}MB/s\n")
    print(f"  网页高速IP已保存: {len(fast_ips)}个 → {filepath}")

# ==================== 主处理函数 ====================
def process_all_sources():
    """处理所有数据源"""
    OUT_DIR.mkdir(exist_ok=True)
    
    # 1. 处理原有源
    print("\n=== 处理原有数据源 ===")
    
    # yongbusi.txt
    print("\n1/6 正在下载处理 yongbusi.txt ...")
    yongbusi_raw = download_raw(URL_YONGBUSI)
    yongbusi_proc = replace_all_speed_tag(yongbusi_raw)
    yongbusi_proc = clean_unwanted_lines(yongbusi_proc)
    with open(OUT_YONGBUSI, "w", encoding="utf-8") as f:
        f.write(yongbusi_proc)
    print(f"yongbusi处理完成 → {OUT_YONGBUSI}")
    
    # Cfxyz.txt
    print("\n2/6 正在下载处理 Cfxyz.txt ...")
    cf_raw = download_raw(URL_CFXYZ)
    cf_proc = replace_all_speed_tag(cf_raw)
    cf_proc = clean_unwanted_lines(cf_proc)
    with open(OUT_CF, "w", encoding="utf-8") as f:
        f.write(cf_proc)
    print(f"Cfxyz处理完成 → {OUT_CF}")
    
    # SG.txt
    print("\n3/6 正在下载处理 SG.txt ...")
    sg_raw = download_raw(URL_SG)
    sg_proc = process_sg(sg_raw)
    sg_proc = clean_unwanted_lines(sg_proc)
    with open(OUT_SG, "w", encoding="utf-8") as f:
        f.write(sg_proc)
    print(f"SG处理完成 → {OUT_SG}")
    
    # 2. 处理新增运营商源
    print("\n=== 处理新增运营商数据源 ===")
    
    # 电信
    print("\n4/6 正在下载处理电信IP...")
    ct_ips = process_operator_url(URL_CT, "电信")
    save_operator_ips(ct_ips, OUT_CT, "电信")
    
    # 联通
    print("\n5/6 正在下载处理联通IP...")
    cu_ips = process_operator_url(URL_CU, "联通")
    save_operator_ips(cu_ips, OUT_CU, "联通")
    
    # 移动
    print("\n6/6 正在下载处理移动IP...")
    cmcc_ips = process_operator_url(URL_CMCC, "移动")
    save_operator_ips(cmcc_ips, OUT_CMCC, "移动")
    
    # 3. 处理网页高速IP
    print("\n=== 处理网页高速IP ===")
    web_fast_ips = extract_fast_ips_from_web(URL_WEB_IP, min_speed=50.0)
    save_web_fast_ips(web_fast_ips, OUT_WEB_IP)
    
    # 4. 合并所有IP
    print("\n=== 合并所有IP ===")
    merge_all_ips(yongbusi_proc, cf_proc, sg_proc, ct_ips, cu_ips, cmcc_ips, web_fast_ips)

def merge_all_ips(yongbusi_txt, cfxyz_txt, sg_txt, ct_ips, cu_ips, cmcc_ips, web_fast_ips):
    """合并所有IP到统一文件"""
    print("\n正在合并所有IP...")
    
    # 准备网页高速IP内容
    web_ip_content = "\n".join([f"{ip['ip']}#{ip['speed']:.2f}MB/s" for ip in web_fast_ips])
    
    # 合并内容
    merge_content = f"""# ============ 原有数据源 ============
# Yongbusi
{yongbusi_txt}

# Cfxyz
{cfxyz_txt}

# SG
{sg_txt}

# ============ 运营商分类IP ============
# 电信 (CT)
{chr(10).join(ct_ips)}

# 联通 (CU)
{chr(10).join(cu_ips)}

# 移动 (CMCC)
{chr(10).join(cmcc_ips)}

# ============ 网页高速IP (速度 > 50MB/s) ============
{web_ip_content}
"""
    
    with open(OUT_MERGE, "w", encoding="utf-8") as f:
        f.write(merge_content)
    
    # 统计信息
    total_ips = 0
    total_ips += len(ip_pattern.findall(yongbusi_txt))
    total_ips += len(ip_pattern.findall(cfxyz_txt))
    total_ips += len(ip_pattern.findall(sg_txt))
    total_ips += len(ct_ips)
    total_ips += len(cu_ips)
    total_ips += len(cmcc_ips)
    total_ips += len(web_fast_ips)
    
    print(f"✅ 合并完成！")
    print(f"   总IP数: {total_ips}")
    print(f"   输出文件: {OUT_MERGE}")

def main():
    """主函数"""
    print("=" * 60)
    print("Cloudflare IP 多源聚合工具 (修改版)")
    print("=" * 60)
    print(f"输出目录: {OUT_DIR.absolute()}")
    print()
    
    try:
        process_all_sources()
        print("\n" + "=" * 60)
        print("✅ 所有处理完成！")
        print("=" * 60)
        
        # 打印输出文件列表
        print("\n输出文件列表:")
        output_files = [
            OUT_YONGBUSI, OUT_CF, OUT_SG,
            OUT_CT, OUT_CU, OUT_CMCC,
            OUT_WEB_IP, OUT_MERGE
        ]
        
        for filepath in output_files:
            if filepath.exists():
                size = filepath.stat().st_size
                print(f"  {filepath.name:30s} {size:>8,} bytes")
        
    except KeyboardInterrupt:
        print("\n\n⚠️ 用户中断处理")
    except Exception as e:
        print(f"\n❌ 处理过程中出现错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
