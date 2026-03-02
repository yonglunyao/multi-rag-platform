#!/usr/bin/env python3
"""
阿里云 DDNS 动态解析脚本（简化版）

支持通过阿里云 API 自动更新域名解析
"""
import requests
import json
import hmac
import base64
import hashlib
from datetime import datetime, timezone
from urllib.parse import quote

# ============= 配置区域 =============
DOMAIN = "m.ohos.asia"          # 完整域名
SUBDOMAIN = "m"                   # 子域名
RECORD_ID = ""                    # 记录ID（首次自动获取）
ACCESS_KEY_ID = ""                # 阿里云 AccessKey ID
ACCESS_KEY_SECRET = ""            # 阿里云 AccessKey Secret
REGION = "cn-hangzhou"             # 地域
TTL = 600                          # DNS 缓存时间（秒）
CONFIG_FILE = "/root/.aliyun_ddns_config.json"  # 配置文件路径
# =================================

log_prefix = "[AliyunDDNS]"


def log(msg):
    """输出日志"""
    print(f"{log_prefix} {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}")


def load_config():
    """加载配置"""
    global RECORD_ID, ACCESS_KEY_ID, ACCESS_KEY_SECRET

    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)
            RECORD_ID = config.get('record_id', '')
            ACCESS_KEY_ID = config.get('access_key_id', '')
            ACCESS_KEY_SECRET = config.get('access_key_secret', '')
        log("配置已加载")
        return True
    except FileNotFoundError:
        log("配置文件不存在，使用默认值")
        return False


def save_config():
    """保存配置"""
    config = {
        'record_id': RECORD_ID,
        'access_key_id': ACCESS_KEY_ID,
        'access_key_secret': ACCESS_KEY_SECRET
    }
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)
    log("配置已保存")


def get_public_ip():
    """获取公网 IP"""
    try:
        # 尝试多个服务
        for url in [
            'https://ifconfig.me',
            'https://api.ipify.org',
            'https://ip.sb'
        ]:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                ip = response.text.strip()
                if ip and len(ip.split('.')) == 4:
                    return ip
    except Exception as e:
        log(f"获取公网IP失败: {e}")

    return None


def sign_request(params, method='GET', timestamp=None):
    """生成阿里云 API 签名"""
    if timestamp is None:
        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # 构造待签名字符串
    canonicalized_query = '&'.join(
        f"{k}={quote(str(v), safe='')}" for k, v in sorted(params.items())
    )

    string_to_sign = f"{method}&%2F&%2F&" + quote(canonicalized_query, safe='').replace('%20', '+')

    # 计算 HMAC-SHA256
    key = f"ACS3-HMAC-SHA256&{ACCESS_KEY_SECRET}"
    digest = hmac.new(key.encode('utf-8'), string_to_sign.encode('utf-8'), hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode('utf-8').replace('+', '%2B').replace('=', '%3D')

    return f"Signature={signature}&Timestamp={timestamp}"


def get_record_id():
    """获取解析记录 ID"""
    global RECORD_ID

    if RECORD_ID:
        return RECORD_ID

    log("首次运行，获取记录ID...")

    # 解析域名
    parts = DOMAIN.split('.')
    maindomain = '.'.join(parts[1:])

    params = {
        'Action': 'DescribeSubDomainRecords',
        'MainDomain': maindomain,
        'SubDomain': SUBDOMAIN,
        'Type': 'A'
    }

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f"https://alidns.{REGION}.aliyuncs.com/"

    query_string = '&'.join(f"{k}={quote(str(v), safe='')}" for k, v in params.items())
    signature_part = sign_request(params, 'GET', timestamp)

    full_url = f"{url}?{query_string}&AccessKeyId={ACCESS_KEY_ID}&SignatureVersion=1.0&{signature_part}"

    try:
        response = requests.get(full_url, timeout=30)
        data = response.json()

        if 'RecordId' in str(data):
            # 从响应中提取 RecordId
            records = data.get('SubDomainRecords', {}).get('Record', [])
            if records:
                RECORD_ID = records[0].get('RecordId')
                log(f"获取到记录ID: {RECORD_ID}")
                save_config()
                return RECORD_ID

        log(f"错误: 未找到 {DOMAIN} 的 A 记录，请先在阿里云控制台创建")
        return None

    except Exception as e:
        log(f"获取记录ID失败: {e}")
        return None


def update_dns(new_ip):
    """更新 DNS 解析"""
    if not RECORD_ID:
        RECORD_ID = get_record_id()
        if not RECORD_ID:
            return False

    params = {
        'Action': 'UpdateDomainRecord',
        'RecordId': RECORD_ID,
        'RR': '@',
        'Type': 'A',
        'Value': new_ip,
        'TTL': TTL
    }

    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    url = f"https://alidns.{REGION}.aliyuncs.com/"

    # POST 请求
    query_string = '&'.join(f"{k}={quote(str(v), safe='')}" for k, v in params.items())
    signature_part = sign_request(params, 'POST', timestamp)

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    post_data = f"{signature_part}&{query_string}"
    full_url = f"{url}?AccessKeyId={ACCESS_KEY_ID}&SignatureVersion=1.0&{post_data}"

    try:
        response = requests.post(full_url, headers=headers, timeout=30)
        data = response.json()

        if data.get('Code') == '200':
            log(f"DNS 更新成功: {DOMAIN} -> {new_ip}")
            return True
        else:
            log(f"DNS 更新失败: {data.get('Message', 'Unknown error')}")
            return False

    except Exception as e:
        log(f"DNS 更新异常: {e}")
        return False


def check_ip_change():
    """检查 IP 是否变化"""
    current_ip = get_public_ip()
    if not current_ip:
        log("无法获取公网 IP")
        return False

    log(f"当前公网 IP: {current_ip}")

    # 查询当前 DNS 解析
    try:
        import socket
        current_dns = socket.gethostbyname(DOMAIN)
        log(f"当前 DNS 解析: {current_dns}")

        if current_ip == current_dns:
            log("IP 未变化，无需更新")
            return True
        else:
            log(f"IP 已变化: {current_dns} -> {current_ip}")
            return update_dns(current_ip)
    except Exception as e:
        log(f"查询 DNS 失败: {e}，尝试直接更新")
        return update_dns(current_ip)


def main():
    """主函数"""
    log("="*50)
    log("阿里云 DDNS 动态解析")
    log("="*50)
    log(f"域名: {DOMAIN}")
    log("")

    # 检查配置
    if not ACCESS_KEY_ID or not ACCESS_KEY_SECRET:
        log("错误: 请配置阿里云 AccessKey")
        log("")
        log("配置步骤:")
        log("1. 访问 https://ram.console.aliyun.com/manage/ak")
        log("2. 创建或查看 AccessKey")
        log("3. 修改脚本中的 ACCESS_KEY_ID 和 ACCESS_KEY_SECRET")
        return

    # 加载配置
    load_config()

    # 检查并更新
    check_ip_change()

    log("")
    log("="*50)
    log("完成！")
    log("="*50)


if __name__ == '__main__':
    main()
