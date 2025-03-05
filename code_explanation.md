# Web Snapshot 模块代码详解

本文将详细解析 Web Snapshot 模块的实现原理和关键代码。这个模块主要用于捕获网页完整截图，特别优化了对动态加载内容的处理。

## 1. 模块概述

`snapshot.py` 是一个功能完整的网页截图工具，它使用 Selenium 和 Chrome WebDriver 来模拟真实浏览器行为，确保能够捕获到动态加载的内容。

### 1.1 核心依赖

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
```

这些依赖提供了与浏览器交互的核心功能。

## 2. 类设计

### 2.1 初始化

```python
def __init__(self, output_dir='snapshotFile', log_level='INFO', wait_time=None):
    self.output_dir = output_dir
    self.wait_time = wait_time
    self.setup_logging(log_level)
    self.setup_driver()
```

构造函数设计考虑了三个关键参数：
- `output_dir`: 输出目录
- `log_level`: 日志级别
- `wait_time`: 可选的等待时间

### 2.2 浏览器配置

```python
def setup_driver(self):
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # 无界面模式
    chrome_options.add_argument('--start-maximized')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--page-load-strategy=normal')
    
    self.driver = webdriver.Chrome(options=chrome_options)
    self.driver.set_window_size(1920, 1080)
```

这部分代码配置了 Chrome 浏览器的运行环境，特别注意：
- 使用无界面模式提高性能
- 设置合适的窗口大小
- 配置页面加载策略

## 3. 智能等待机制

### 3.1 渐进式滚动

```python
def scroll_to_bottom(self):
    self.logger.info("Starting progressive scroll to trigger lazy loading...")
    last_height = self.driver.execute_script("return document.body.scrollHeight")
    
    while True:
        # 渐进式滚动
        for i in range(1, 10):
            self.driver.execute_script(
                f"window.scrollTo(0, document.body.scrollHeight * {i/10});"
            )
            time.sleep(0.5)
        
        # 检查是否到达底部
        new_height = self.driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            break
        last_height = new_height
```

这个方法通过渐进式滚动来触发懒加载内容：
- 分10次渐进滚动到底部
- 每次滚动后短暂等待
- 检测页面高度变化

### 3.2 内容稳定性检测

```python
def wait_for_content_stable(self, timeout=10):
    self.logger.info("Waiting for content to stabilize...")
    start_time = time.time()
    last_height = 0
    
    while time.time() - start_time < timeout:
        current_height = self.driver.execute_script(
            "return document.body.scrollHeight"
        )
        if current_height == last_height:
            time.sleep(2)
            return True
        last_height = current_height
        time.sleep(1)
    
    return False
```

通过监控页面高度变化来判断内容是否稳定：
- 设置超时机制
- 持续检测高度变化
- 确认稳定后额外等待

### 3.3 动态内容检测

```python
def wait_for_dynamic_content(self):
    try:
        # 检查 AJAX 请求
        script = """
            return (window.jQuery != null && jQuery.active == 0) || 
                   (typeof fetch === 'function' && 
                    performance.getEntriesByType('resource').length > 0);
        """
        WebDriverWait(self.driver, 5).until(
            lambda driver: driver.execute_script(script)
        )
        
        # 监控 DOM 变化
        script = """
            let observer;
            let changes = 0;
            let resolve;
            
            const promise = new Promise(r => resolve = r);
            
            observer = new MutationObserver(() => {
                changes++;
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true
            });
            
            setTimeout(() => {
                observer.disconnect();
                resolve(changes);
            }, 1000);
            
            return promise;
        """
        
        changes = self.driver.execute_script(script)
        return changes == 0
        
    except Exception as e:
        self.logger.debug(f"Error checking dynamic content: {str(e)}")
        return False
```

这个方法综合使用多种技术来检测动态内容：
- 检查 AJAX 请求状态
- 使用 MutationObserver 监控 DOM 变化
- 设置观察超时时间

## 4. 截图核心流程

```python
def capture_screenshot(self, url):
    try:
        self.driver.get(url)
        
        # 1. 等待基本加载
        WebDriverWait(self.driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, 'body'))
        )
        
        # 2. 触发懒加载
        self.scroll_to_bottom()
        
        # 3. 等待内容稳定
        content_stable = self.wait_for_content_stable()
        
        # 4. 等待图片加载
        self.wait_for_images()
        
        # 5. 检查动态内容
        dynamic_content_loaded = self.wait_for_dynamic_content()
        
        # 6. 智能等待
        if self.wait_time is not None or not (content_stable and dynamic_content_loaded):
            wait_time = self.wait_time if self.wait_time is not None else 3
            time.sleep(wait_time)
        
        # 7. 设置最终尺寸
        total_height = self.driver.execute_script("""
            return Math.max(
                document.body.scrollHeight,
                document.body.offsetHeight,
                document.documentElement.clientHeight,
                document.documentElement.scrollHeight,
                document.documentElement.offsetHeight
            );
        """)
        
        viewport_width = self.driver.execute_script("""
            return Math.max(
                document.body.scrollWidth,
                document.body.offsetWidth,
                document.documentElement.clientWidth,
                document.documentElement.scrollWidth,
                document.documentElement.offsetWidth
            );
        """)
        
        # 8. 捕获截图
        self.driver.set_window_size(viewport_width + 100, total_height + 100)
        screenshot_path = os.path.join(self.output_dir, f"snapshot_{timestamp}.png")
        self.driver.save_screenshot(screenshot_path)
        
        return screenshot_path, json_path
        
    except Exception as e:
        self.logger.error(f"Error capturing screenshot: {str(e)}")
        return None
```

截图过程包含多个关键步骤：
1. 页面基本加载
2. 触发懒加载内容
3. 等待内容稳定
4. 确保图片加载完成
5. 检查动态内容
6. 智能等待策略
7. 计算最终页面尺寸
8. 生成截图和元数据

## 5. 错误处理

模块实现了完整的错误处理机制：
- 使用 try-except 捕获所有可能的异常
- 详细的日志记录
- 优雅的资源清理
- 合适的返回值处理

## 6. 使用建议

### 6.1 基本使用
```python
snapshot = WebSnapshot()
result = snapshot.capture_screenshot('https://example.com')
```

### 6.2 高级配置
```python
snapshot = WebSnapshot(
    output_dir='custom_dir',
    log_level='DEBUG',
    wait_time=10  # 特殊情况下使用
)
```

### 6.3 错误处理
```python
try:
    result = snapshot.capture_screenshot(url)
    if result:
        screenshot_path, json_path = result
        print(f"成功：{screenshot_path}")
    else:
        print("截图失败")
finally:
    snapshot.close()
```

## 总结

Web Snapshot 模块通过综合运用多种技术，实现了可靠的网页截图功能：
- 智能等待机制确保内容完整性
- 渐进式滚动触发懒加载
- 多重检测保证动态内容加载
- 完善的错误处理和日志记录
- 灵活的配置选项

这些特性使得该模块能够处理各种复杂的网页场景，特别是对于包含大量动态加载内容的现代网页。 