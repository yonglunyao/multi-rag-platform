# 阿里云 DDNS 配置指南

将公网 IP 动态解析到 `m.ohos.asia`

## 前提条件

1. 拥有 `ohos.asia` 域名的管理权限
2. 已在阿里云 DNS 控制台创建 `m.ohos.asia` 的 A 记录

## 配置步骤

### 1. 创建阿里云 AccessKey

1. 访问 [RAM 控制台](https://ram.console.aliyun.com/manage/ak)
2. 创建 AccessKey
3. 保存 AccessKey ID 和 AccessKey Secret

### 2. 首次手动创建解析记录

在阿里云 DNS 控制台手动创建：
- 主机记录: `@`
- 记录类型: `A`
- 记录值: `153.3.118.96` (当前公网 IP)
- TTL: `600`

### 3. 配置脚本

编辑 `scripts/aliyun_ddns.py`，填写配置：

```python
DOMAIN = "m.ohos.asia"          # 完整域名
SUBDOMAIN = "m"                   # 子域名
ACCESS_KEY_ID = "你的AccessKeyID"
ACCESS_KEY_SECRET = "你的AccessKeySecret"
REGION = "cn-hangzhou"             # 地域
```

### 4. 测试脚本

```bash
python3 scripts/aliyun_ddns.py
```

输出示例：
```
[AliyunDDNS] 2026-03-02 08:00:00 ========================================
[AliyunDDNS] 2026-03-02 08:00:00 阿里云 DDNS 动态解析
[AliyunDDNS] 2026-03-02 08:00:00 ========================================
[AliyunDDNS] 2026-03-02 08:00:00 域名: m.ohos.asia
[AliyunDDNS] 2026-03-02 08:00:00 当前公网 IP: 153.3.118.96
[AliyunDDNS] 2026-03-02 08:00:00 获取到记录ID: 123456789
[AliyunDDNS] 2026-03-02 08:00:00 DNS 更新成功: m.ohos.asia -> 153.3.118.96
```

### 5. 设置定时任务（自动更新）

编辑 crontab：

```bash
crontab -e
```

添加以下内容（每 5 分钟检查一次）：

```cron
*/5 * * * * /usr/bin/python3 /home/mind/workspace/harmony-docs-rag/scripts/aliyun_ddns.py >> /var/log/aliyun_ddns.log 2>&1
```

或使用 systemd timer（推荐）：

```bash
# 创建服务文件
sudo cp /home/mind/workspace/harmony-docs-rag/scripts/aliyun-ddns.service /etc/systemd/system/
sudo systemctl enable aliyun-ddns.service
sudo systemctl start aliyun-ddns.service
```

## 使用方法

### 手动更新
```bash
python3 scripts/aliyun_ddns.py
```

### 查看日志
```bash
tail -f /var/log/aliyun_ddns.log
```

### 查看 DNS 解析
```bash
dig m.ohos.asia
nslookup m.ohos.asia
curl ifconfig.me
```

## 故障排查

### 1. 权限不足
确保 AccessKey 具有阿里云 DNS 写权限

### 2. 记录不存在
确保已在阿里云控制台手动创建 A 记录

### 3. IP 获取失败
检查网络连接，确保能访问公网

### 4. 更新失败
检查日志文件，查看具体错误信息

## 当前公网 IP

```bash
curl ifconfig.me
# 输出: 153.3.118.96
```
