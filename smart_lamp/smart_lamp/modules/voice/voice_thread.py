#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音处理线程
简化版：直接使用 VoiceRecognizer
"""
import threading
import time
from typing import Optional
from queue import Queue, Empty

from .voice_recognizer import VoiceRecognizer


class VoiceThread(threading.Thread):
    """
    语音处理线程
    持续监听麦克风，将识别结果放入队列
    """
    
    def __init__(self, config: dict):
        super().__init__(daemon=True, name="VoiceThread")
        
        self.config = config
        self._running = False
        
        # 识别结果队列
        self._result_queue: Queue = Queue()
        
        # 从配置获取 API 参数
        voice_config = config.get('modules', {}).get('voice', {})
        
        self.recognizer = VoiceRecognizer(
            app_id=voice_config.get('app_id', ''),
            api_key=voice_config.get('api_key', ''),
            api_secret=voice_config.get('api_secret', '')
        )
    
    def run(self):
        """线程主循环"""
        print("[Voice] 语音线程启动")
        self._running = True
        
        # 启动识别器
        self.recognizer.start(
            on_result=self._on_result,
            on_error=self._on_error
        )
        
        # 保持线程运行
        while self._running:
            time.sleep(0.1)
        
        # 停止识别器
        self.recognizer.stop()
        print("[Voice] 语音线程退出")
    
    def _on_result(self, text: str):
        """识别结果回调"""
        text = text.strip()
        if text:
            print(f"[Voice] 识别: {text}")
            self._result_queue.put(text)
    
    def _on_error(self, error: str):
        """错误回调"""
        print(f"[Voice] 错误: {error}")
    
    def get_text(self, timeout: float = 0.0) -> Optional[str]:
        """
        获取识别结果
        
        Args:
            timeout: 超时时间，0表示不等待
            
        Returns:
            识别到的文本，没有则返回 None
        """
        try:
            if timeout > 0:
                return self._result_queue.get(timeout=timeout)
            else:
                return self._result_queue.get_nowait()
        except Empty:
            return None
    
    def clear_results(self):
        """清空结果队列"""
        while not self._result_queue.empty():
            try:
                self._result_queue.get_nowait()
            except Empty:
                break
    
    def stop(self):
        """停止线程"""
        self._running = False
        self.recognizer.stop()
    
    @property
    def is_connected(self) -> bool:
        """是否正在运行"""
        return self._running and self.recognizer.is_running


# 测试
def test_voice_thread():
    """测试语音线程"""
    print("=" * 50)
    print("语音线程测试")
    print("=" * 50)
    
    config = {
        'modules': {
            'voice': {
                'app_id': 'cac00df6',
                'api_key': 'b44a5920313b3b3302e918ba97e17450',
                'api_secret': 'NjJmMjdjMzMyNDFhYjY3YWM2NWI3NzZh',
            }
        }
    }
    
    voice = VoiceThread(config)
    voice.start()
    
    print("请说话，按 Ctrl+C 退出")
    
    try:
        while True:
            text = voice.get_text(timeout=0.5)
            if text:
                print(f">>> 收到: {text}")
    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        voice.stop()
        print("测试结束")


if __name__ == "__main__":
    test_voice_thread()
