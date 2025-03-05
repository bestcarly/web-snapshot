# Web Snapshot Module

这是一个用于网页截图的Python模块，可以智能捕获完整网页的截图并生成对应的JSON数据文件。该模块特别优化了对动态加载内容的支持。

## 功能特点

- 支持完整网页截图，包括延迟加载内容
- 智能等待机制，确保动态内容完全加载
- 渐进式滚动触发懒加载内容
- 自动检测页面内容稳定性
- 自动生成对应的JSON数据文件
- 可配置的日志记录
- 命令行界面
- 可作为独立服务被其他业务集成

## 智能等待机制

模块采用多重检测机制确保内容完整性：
1. 渐进式滚动触发懒加载
2. DOM内容稳定性检测
3. 图片加载完成检测
4. AJAX请求完成检测
5. 动态内容变化监控

## 安装要求

- Python 3.7+
- Chrome浏览器
- ChromeDriver（与Chrome浏览器版本匹配）

## 安装步骤

1. 克隆仓库：
```bash
git clone <repository-url>
cd web-snapshot
```

2. 安装依赖：
```bash
pip install -r requirements.txt
```

3. 确保Chrome浏览器已安装

## 使用方法

### 命令行使用

基本用法（使用智能等待）：
```bash
python snapshot.py --url <网页URL>
```

完整参数：
```bash
python snapshot.py --url <网页URL> [--output-dir <输出目录>] [--log-level <日志级别>] [--wait-time <等待时间>]
```

参数说明：
- `--url`: 要截图的网页URL（必需）
- `--output-dir`: 截图和JSON文件的输出目录（默认：snapshotFile）
- `--log-level`: 日志级别（默认：INFO，可选：DEBUG, INFO, WARNING, ERROR, CRITICAL）
- `--wait-time`: 可选的额外等待时间（秒），通常不需要设置，模块会智能判断

### 作为模块集成

```python
from snapshot import WebSnapshot

# 创建WebSnapshot实例（使用智能等待）
snapshot = WebSnapshot(output_dir='snapshotFile', log_level='INFO')

# 或者指定固定等待时间（特殊情况下使用）
# snapshot = WebSnapshot(output_dir='snapshotFile', log_level='INFO', wait_time=10)

try:
    # 捕获截图
    result = snapshot.capture_screenshot('https://example.com')
    if result:
        screenshot_path, json_path = result
        print(f"截图和JSON数据已保存：{screenshot_path}")
finally:
    # 清理资源
    snapshot.close()
```

## 输出文件

### 截图文件
- 格式：PNG
- 位置：`snapshotFile/snapshot_YYYYMMDD_HHMMSS.png`
- 内容：完整的网页截图，包括所有动态加载内容

### JSON数据文件
- 格式：JSON
- 位置：`snapshotFile/snapshot_YYYYMMDD_HHMMSS.json`
- 内容：包含URL、时间戳、页面尺寸、元数据等信息

### 日志文件
- 位置：`logs/snapshot.log`
- 内容：详细的运行记录，包含加载过程、等待状态和错误信息

## 性能优化

模块采用智能等待策略，避免不必要的固定等待时间：
1. 仅在内容不稳定时使用额外等待
2. 动态检测页面加载状态
3. 自适应等待时间

## 注意事项

1. 确保系统已安装Chrome浏览器
2. 确保网络连接正常
3. 某些网页可能需要登录或有其他访问限制
4. 对于特别复杂的动态页面，可能需要使用 `wait_time` 参数
5. 建议定期清理输出目录和日志文件

## 错误处理

模块会记录以下类型的错误：
- 页面加载超时
- 截图失败
- 文件保存错误
- 动态内容加载失败
- DOM操作异常
- 其他运行时异常

所有错误都会被记录到日志文件中，并返回适当的错误信息。

## 调试建议

如果遇到截图不完整的情况：
1. 使用 DEBUG 日志级别查看详细加载过程
2. 检查网页是否有特殊的动态加载机制
3. 适当增加 wait_time 参数值
4. 查看日志文件中的警告和错误信息

## 许可证

MIT License 