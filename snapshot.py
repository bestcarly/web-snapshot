#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Web Snapshot Module
===================

This module provides functionality to capture full webpage screenshots and generate corresponding JSON data.
It can be used as a standalone service or integrated into other applications.

Features:
- Capture full webpage screenshots with support for lazy-loaded content
- Generate JSON data for each screenshot
- Logging functionality with configurable output
- Command-line interface for easy use
- Configurable screenshot and JSON file storage

Usage:
    python snapshot.py --url <url> [--output-dir <dir>] [--log-level <level>] [--wait-time <seconds>]
"""

import os
import json
import logging
import argparse
import time
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, StaleElementReferenceException
from PIL import Image

class WebSnapshot:
    def __init__(self, output_dir='snapshotFile', log_level='INFO', wait_time=None):
        """
        Initialize the WebSnapshot class.
        
        Args:
            output_dir (str): Directory to store screenshots and JSON files
            log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            wait_time (int, optional): Additional wait time in seconds for content to load.
                                     If None, will use dynamic waiting strategy.
        """
        self.output_dir = output_dir
        self.wait_time = wait_time
        self.setup_logging(log_level)
        self.setup_driver()
        
    def setup_logging(self, log_level):
        """Configure logging settings."""
        log_dir = 'logs'
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
            
        log_file = os.path.join(log_dir, 'snapshot.log')
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        
    def setup_driver(self):
        """Configure and initialize the Chrome WebDriver."""
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run in headless mode
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        # 增加页面渲染等待时间
        chrome_options.add_argument('--page-load-strategy=normal')
        
        self.driver = webdriver.Chrome(options=chrome_options)
        # 设置更大的初始窗口大小
        self.driver.set_window_size(1920, 1080)

    def scroll_to_bottom(self):
        """
        滚动到页面底部以触发懒加载内容。
        使用渐进式滚动以确保内容正确加载。
        """
        self.logger.info("Starting progressive scroll to trigger lazy loading...")
        
        # 获取初始页面高度
        last_height = self.driver.execute_script("return document.body.scrollHeight")
        
        while True:
            # 渐进式滚动
            for i in range(1, 10):
                self.driver.execute_script(f"window.scrollTo(0, document.body.scrollHeight * {i/10});")
                time.sleep(0.5)  # 短暂等待让内容加载
            
            # 滚动到底部
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # 等待新内容加载
            
            # 计算新的页面高度
            new_height = self.driver.execute_script("return document.body.scrollHeight")
            
            # 如果高度没有变化，说明已经到底
            if new_height == last_height:
                break
                
            last_height = new_height
            
        # 回到顶部
        self.driver.execute_script("window.scrollTo(0, 0);")
        self.logger.info("Completed progressive scroll")

    def wait_for_content_stable(self, timeout=10):
        """
        等待页面内容稳定，确保动态内容加载完成。
        
        Args:
            timeout (int): 最大等待时间（秒）
        """
        self.logger.info("Waiting for content to stabilize...")
        
        start_time = time.time()
        last_height = 0
        
        while time.time() - start_time < timeout:
            current_height = self.driver.execute_script("return document.body.scrollHeight")
            if current_height == last_height:
                time.sleep(2)  # 额外等待以确保内容真的稳定
                return True
            last_height = current_height
            time.sleep(1)
            
        return False

    def wait_for_images(self):
        """等待所有图片加载完成"""
        self.logger.info("Waiting for images to load...")
        try:
            script = """
            return Array.from(document.getElementsByTagName('img')).every(img => {
                return img.complete && img.naturalHeight !== 0
            });
            """
            WebDriverWait(self.driver, 10).until(
                lambda driver: driver.execute_script(script)
            )
        except TimeoutException:
            self.logger.warning("Timeout waiting for images to load")

    def wait_for_dynamic_content(self):
        """
        智能等待动态内容加载完成。
        综合检查多个指标来确定页面是否加载完成。
        """
        self.logger.info("Checking for dynamic content loading...")
        
        try:
            # 等待 AJAX 请求完成
            script = """
                return (window.jQuery != null && jQuery.active == 0) || 
                       (typeof fetch === 'function' && performance.getEntriesByType('resource').length > 0);
            """
            WebDriverWait(self.driver, 5).until(
                lambda driver: driver.execute_script(script)
            )
            
            # 检查 DOM 变化是否停止
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
            if changes == 0:
                self.logger.info("No DOM changes detected, content appears stable")
                return True
                
            return False
            
        except Exception as e:
            self.logger.debug(f"Error checking dynamic content: {str(e)}")
            return False

    def capture_screenshot(self, url):
        """
        Capture a full webpage screenshot and generate JSON data.
        
        Args:
            url (str): The URL of the webpage to capture
            
        Returns:
            tuple: (screenshot_path, json_path) if successful, None if failed
        """
        try:
            self.logger.info(f"Starting screenshot capture for URL: {url}")
            
            # Navigate to the URL
            self.driver.get(url)
            
            # 等待页面基本元素加载
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, 'body'))
            )
            
            # 执行滚动操作触发懒加载
            self.scroll_to_bottom()
            
            # 等待内容稳定
            content_stable = self.wait_for_content_stable()
            
            # 等待图片加载
            self.wait_for_images()
            
            # 检查动态内容
            dynamic_content_loaded = self.wait_for_dynamic_content()
            
            # 如果设置了额外等待时间，或者内容不稳定，则等待
            if self.wait_time is not None or not (content_stable and dynamic_content_loaded):
                wait_time = self.wait_time if self.wait_time is not None else 3
                self.logger.info(f"Waiting additional {wait_time} seconds for content to stabilize")
                time.sleep(wait_time)
            
            # 获取最终的页面尺寸
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
            
            # 设置窗口大小以捕获完整内容
            self.driver.set_window_size(viewport_width + 100, total_height + 100)
            
            # 再次等待以确保调整大小后的内容正确加载
            time.sleep(2)
            
            # Generate timestamp for unique filenames
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"snapshot_{timestamp}"
            
            # Capture screenshot
            screenshot_path = os.path.join(self.output_dir, f"{filename}.png")
            self.driver.save_screenshot(screenshot_path)
            
            # Generate JSON data
            json_data = {
                'url': url,
                'timestamp': timestamp,
                'dimensions': {
                    'width': viewport_width,
                    'height': total_height
                },
                'metadata': {
                    'title': self.driver.title,
                    'url': self.driver.current_url,
                    'user_agent': self.driver.execute_script("return navigator.userAgent")
                }
            }
            
            # Save JSON data
            json_path = os.path.join(self.output_dir, f"{filename}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(json_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"Screenshot and JSON data saved successfully: {filename}")
            return screenshot_path, json_path
            
        except TimeoutException:
            self.logger.error(f"Timeout while loading URL: {url}")
            return None
        except Exception as e:
            self.logger.error(f"Error capturing screenshot: {str(e)}")
            return None
            
    def close(self):
        """Close the WebDriver and clean up resources."""
        if hasattr(self, 'driver'):
            self.driver.quit()
            self.logger.info("WebDriver closed successfully")

def main():
    """Main function to handle command-line interface."""
    parser = argparse.ArgumentParser(description='Web Snapshot Tool')
    parser.add_argument('--url', required=True, help='URL of the webpage to capture')
    parser.add_argument('--output-dir', default='snapshotFile', help='Directory to store screenshots and JSON files')
    parser.add_argument('--log-level', default='INFO', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                      help='Logging level')
    parser.add_argument('--wait-time', type=int, help='Optional additional wait time in seconds for content to load')
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
    
    # Initialize and run the snapshot tool
    snapshot = WebSnapshot(output_dir=args.output_dir, log_level=args.log_level, wait_time=args.wait_time)
    try:
        result = snapshot.capture_screenshot(args.url)
        if result:
            print(f"Screenshot and JSON data saved successfully: {result[0]}")
        else:
            print("Failed to capture screenshot")
    finally:
        snapshot.close()

if __name__ == '__main__':
    main()
