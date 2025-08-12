# 网络配置说明

本应用已针对公司网络环境进行了优化，解决了常见的SSL证书和代理问题。

## 已解决的问题

### 1. SSL证书问题
- 自动禁用SSL证书验证，解决公司网络下的证书信任问题
- 抑制SSL警告信息，保持界面清洁

### 2. 代理支持
- 自动检测系统代理设置
- 支持HTTP和HTTPS代理
- 从环境变量自动获取代理配置

## 代理配置方法

### 方法一：设置环境变量（推荐）

在Windows系统中设置以下环境变量：

```bash
# 设置HTTP代理
set HTTP_PROXY=http://proxy.company.com:8080

# 设置HTTPS代理
set HTTPS_PROXY=http://proxy.company.com:8080

# 或者使用小写形式
set http_proxy=http://proxy.company.com:8080
set https_proxy=http://proxy.company.com:8080
```

### 方法二：在启动脚本中设置

修改 `run.bat` 文件，在启动应用前设置代理：

```batch
@echo off
echo 正在配置网络环境...

# 设置代理（请替换为实际的代理地址和端口）
set HTTP_PROXY=http://proxy.company.com:8080
set HTTPS_PROXY=http://proxy.company.com:8080

echo 正在安装依赖...
pip install -r requirements.txt

echo 正在启动命令管理器...
python main.py
pause
```

### 方法三：系统代理设置

应用会自动使用Windows系统的代理设置，无需额外配置。

## 网络功能

### 音乐播放器
- 支持网易云歌单加载
- 自动处理SSL证书问题
- 支持代理环境下的音频流播放
- 优化了网络请求超时和重试机制

### 网络请求特性
- 统一的session管理
- 自动代理检测和配置
- SSL验证禁用
- 合理的超时设置
- 标准User-Agent头

## 故障排除

### 如果仍然无法连接网络：

1. **检查代理设置**：确认代理地址和端口正确
2. **检查防火墙**：确保应用被允许访问网络
3. **检查网络连接**：确认基本网络连接正常
4. **联系IT部门**：获取正确的代理配置信息

### 常见错误解决：

- `ConnectionError`: 检查网络连接和代理设置
- `SSLError`: 已自动处理，如仍出现请联系开发者
- `TimeoutError`: 网络较慢，应用会自动重试
- `ProxyError`: 检查代理服务器是否可用

## 技术细节

- 使用requests.Session进行统一的网络请求管理
- 自动从环境变量读取代理配置
- 禁用urllib3的InsecureRequestWarning警告
- 设置合理的超时时间和重试机制

---

如有其他网络问题，请联系技术支持。