#!/bin/bash
# 阿里云 DDNS 动态解析脚本
# 将出口 IP 自动更新到阿里云域名解析

# 配置信息
DOMAIN="m.ohos.asia"
RECORD_ID=""  # 从阿里云获取，首次运行后会自动保存
SUBDOMAIN="m"
RR="@"
REGION="cn-hangzhou"  # 根据实际情况修改
ACCESS_KEY_ID=""  # 阿里云 AccessKey ID
ACCESS_KEY_SECRET=""  # 阿里云 AccessKey Secret
CONFIG_FILE="/root/.aliyun_ddns_config.json"
TTL=600  # DNS 缓存时间（秒）

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# 获取公网 IP
get_public_ip() {
    local ip
    ip=$(curl -s --interface enp7s0 ifconfig.me 2>/dev/null || curl -s ifconfig.me 2>/dev/null)
    echo "$ip"
}

# 从配置文件读取
load_config() {
    if [ -f "$CONFIG_FILE" ]; then
        RECORD_ID=$(grep -o '"record_id"[^,]*' "$CONFIG_FILE" | cut -d'"' -f4)
        ACCESS_KEY_ID=$(grep -o '"access_key_id"[^,]*' "$CONFIG_FILE" | cut -d'"' -f4)
        ACCESS_KEY_SECRET=$(grep -o '"access_key_secret"[^,]*' "$CONFIG_FILE" | cut -d'"' -f4)
        log("配置已加载")
    fi
}

# 保存配置
save_config() {
    cat > "$CONFIG_FILE" << EOF
{
    "record_id": "$RECORD_ID",
    "access_key_id": "$ACCESS_KEY_ID",
    "access_key_secret": "$ACCESS_KEY_SECRET"
}
EOF
    log("配置已保存")
}

# 获取阿里云 API 签名
aliyun_api_signature() {
    local method="$1"
    local params="$2"
    local timestamp="$3"

    # 构造签名字符串
    local string_to_sign="${method}&%2F&"
    local canonicalized_query=$(echo "$params" | sed 's/&/\%26/g' | sed 's/=/%3D/g' | sed 's/:/%3A/g' | tr '&' '\n' | sort | tr '\n' '&' | sed 's/&$//')

    # 加密密钥
    local date_key=$(echo -n "$timestamp" | openssl dgst -sha256 -hmac "sha256" -binary -key "$ACCESS_KEY_SECRET" | od -An -v1 | sed 's/ //g' | tr -d '\n' | xxd -r -p | base64)
    local date_signed_key=$(echo -n "ACS3-HMAC-SHA256" | xxd -r -p | cat <(echo -n "$date_key" | xxd -r -p) | openssl dgst -sha256 -hmac "sha256" -binary -binary | base64)
    local canonicalized_query_key=$(echo -n "$canonicalized_query" | openssl dgst -sha256 -hmac "sha256" -binary -key "$date_signed_key" -binary | base64)

    # 签名
    local signature_string_to_sign="GET&%2F&%2F${date_signed_key}&${canonicalized_query_key}"
    local signature=$(echo -n "$signature_string_to_sign" | openssl dgst -sha256 -hmac "sha256" -binary -key "$ACCESS_KEY_SECRET" | od -An -v1 | sed 's/ //g' | tr -d '\n' | xxd -r -p | base64)

    echo "$signature"
}

# 获取记录 ID
get_record_id() {
    if [ -z "$RECORD_ID" ]; then
        log("首次运行，获取记录 ID...")

        # 获取二级域名
        local subdomain=$(echo "$DOMAIN" | cut -d'.' -f1)
        local maindomain=$(echo "$DOMAIN" | cut -d'.' -f2-)

        # 查询现有解析记录
        local url="https://alidns.${REGION}.aliyuncs.com/?Action=DescribeSubDomainRecords&MainDomain=${maindomain}&SubDomain=${subdomain}&Type=A"
        local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
        local signature=$(aliyun_api_signature "GET" "Action=DescribeSubDomainRecords&MainDomain=${maindomain}&SubDomain=${subdomain}&Type=A&Timestamp=${timestamp}" "$timestamp")

        local response=$(curl -s "$url&Signature=$signature&AccessKeyId=$ACCESS_KEY_ID&SignatureVersion=1.0&Timestamp=${timestamp}")

        # 解析 RecordId
        RECORD_ID=$(echo "$response" | grep -o '"RecordId"[^,]*' | head -1 | cut -d'"' -f4)

        if [ -z "$RECORD_ID" ]; then
            log("错误: 未找到解析记录，请先在阿里云控制台手动创建 $DOMAIN 的 A 记录")
            exit 1
        fi

        log("获取到记录 ID: $RECORD_ID")
        save_config
    fi
}

# 更新 DNS 解析
update_dns() {
    local new_ip="$1"
    local current_ip=$(dig +short $DOMAIN @dns9.quad9.net 2>/dev/null | head -1)

    if [ "$new_ip" = "$current_ip" ]; then
        log("IP 未变化: $new_ip，无需更新")
        return 0
    fi

    log("IP 已变化: $current_ip -> $new_ip，开始更新...")

    # 调用阿里云 API 更新解析
    local url="https://alidns.${REGION}.aliyuncs.com/?Action=UpdateDomainRecord&RecordId=${RECORD_ID}&RR=${RR}&Type=A&Value=${new_ip}&TTL=${TTL}"
    local timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    local params="Action=UpdateDomainRecord&RecordId=${RECORD_ID}&RR=${RR}&TTL=${TTL}&Timestamp=${timestamp}&Type=A&Value=${new_ip}"
    local signature=$(aliyun_api_signature "POST" "$params" "$timestamp")

    local response=$(curl -s -X POST "$url" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "Signature=$signature&AccessKeyId=$ACCESS_KEY_ID&SignatureVersion=1.0&Timestamp=${timestamp}" \
        -d "$params")

    if echo "$response" | grep -q '"Code":"200"'; then
        log("DNS 更新成功: $DOMAIN -> $new_ip")
    else
        log("DNS 更新失败")
        log("响应: $response")
        return 1
    fi
}

# 主函数
main() {
    log "========================================"
    log "阿里云 DDNS 更新脚本"
    log "========================================"
    log "域名: $DOMAIN"
    log ""

    # 检查配置
    if [ -z "$ACCESS_KEY_ID" ] || [ -z "$ACCESS_KEY_SECRET" ]; then
        log "错误: 请配置阿里云 AccessKey"
        log ""
        echo "配置方法:"
        echo "1. 访问阿里云控制台 > AccessKey 管理"
        echo "2. 创建 AccessKey"
        echo "3. 修改脚本中的 ACCESS_KEY_ID 和 ACCESS_KEY_SECRET"
        exit 1
    fi

    # 加载配置
    load_config

    # 获取公网 IP
    local current_ip=$(get_public_ip)
    log "当前公网 IP: $current_ip"

    # 首次运行，获取记录 ID
    get_record_id

    # 更新 DNS
    update_dns "$current_ip"

    log "========================================"
    log "完成！"
    log "========================================"
}

main "$@"
