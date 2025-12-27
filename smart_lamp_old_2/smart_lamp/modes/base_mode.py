"""
模式基类 - 所有功能模式的抽象基类
"""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import time


class BaseMode(ABC):
    """
    模式基类
    所有功能模式（手部跟随、桌宠、亮度调节）都继承此类
    """
    
    # 模式名称（子类重写）
    MODE_NAME = "基础模式"
    
    def __init__(self, controller):
        """
        初始化模式
        
        Args:
            controller: 主控制器引用，用于访问硬件
        """
        self.controller = controller
        self._active = False
        self._start_time: Optional[float] = None
        
    @property
    def is_active(self) -> bool:
        """模式是否激活"""
        return self._active
    
    @property
    def duration(self) -> float:
        """模式运行时长（秒）"""
        if self._start_time:
            return time.time() - self._start_time
        return 0.0
    
    def enter(self):
        """
        进入模式
        子类可以重写以执行初始化操作
        """
        self._active = True
        self._start_time = time.time()
        self._print(f"进入 [{self.MODE_NAME}]")
        self.on_enter()
    
    def exit(self):
        """
        退出模式
        子类可以重写以执行清理操作
        """
        self._print(f"退出 [{self.MODE_NAME}]，运行时长: {self.duration:.1f}秒")
        self.on_exit()
        self._active = False
        self._start_time = None
    
    @abstractmethod
    def on_enter(self):
        """进入模式时的回调（子类实现）"""
        pass
    
    @abstractmethod
    def on_exit(self):
        """退出模式时的回调（子类实现）"""
        pass
    
    @abstractmethod
    def update(self, frame=None, voice_text: str = None) -> bool:
        """
        更新模式（主循环调用）
        
        Args:
            frame: 摄像头帧（如果视觉相关模式需要）
            voice_text: 语音识别文本（如果有）
            
        Returns:
            是否继续运行。返回 False 则退出模式
        """
        pass
    
    def handle_voice(self, text: str) -> bool:
        """
        处理语音命令
        
        Args:
            text: 语音识别文本
            
        Returns:
            是否处理了该命令
        """
        # 默认不处理，子类可以重写
        return False
    
    def _print(self, message: str):
        """格式化打印"""
        print(f"[{self.MODE_NAME}] {message}")
    
    def _debug(self, message: str):
        """调试打印"""
        if self.controller and getattr(self.controller, 'debug', False):
            print(f"[{self.MODE_NAME}][DEBUG] {message}")
