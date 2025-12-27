"""
命令解析器
将识别的文本解析为具体命令
"""
from typing import Optional, Dict, List


class CommandParser:
    """
    命令解析器
    将自然语言转换为结构化命令
    """
    
    def __init__(self):
        """初始化命令解析器"""
        # 命令关键词映射
        self.command_patterns = {
            # 开关灯
            '开灯': {'action': 'light_on'},
            '打开': {'action': 'light_on'},
            '开启': {'action': 'light_on'},
            '关灯': {'action': 'light_off'},
            '关闭': {'action': 'light_off'},
            '关掉': {'action': 'light_off'},
            
            # 亮度调节
            '亮一点': {'action': 'brightness_up'},
            '调亮': {'action': 'brightness_up'},
            '暗一点': {'action': 'brightness_down'},
            '调暗': {'action': 'brightness_down'},
            '最亮': {'action': 'brightness_max'},
            '最暗': {'action': 'brightness_min'},
            
            # 动作
            '蹦迪': {'action': 'dance'},
            '跳舞': {'action': 'dance'},
            '点头': {'action': 'nod'},
            '点点头': {'action': 'nod'},
            '摇头': {'action': 'shake'},
            '摇摇头': {'action': 'shake'},
            '卖萌': {'action': 'cute'},
            '可爱': {'action': 'cute'},
            '打招呼': {'action': 'wave'},
            '你好': {'action': 'wave'},
            
            # 系统
            '停止': {'action': 'stop'},
            '停下': {'action': 'stop'},
            '休息': {'action': 'sleep'},
        }
        
        # 同音词/错误词修正
        self.corrections = {
            '开机': '开灯',
            '关机': '关灯',
            '凯灯': '开灯',
            '光灯': '关灯',
        }
    
    def parse(self, text: str) -> Optional[Dict]:
        """
        解析文本为命令
        
        Args:
            text: 识别的文本
            
        Returns:
            命令字典或 None
        """
        if not text:
            return None
        
        # 清理文本
        text = text.strip()
        
        # 同音词修正
        for wrong, correct in self.corrections.items():
            if wrong in text:
                text = text.replace(wrong, correct)
        
        # 查找匹配的命令
        for keyword, command in self.command_patterns.items():
            if keyword in text:
                return {
                    'command': keyword,
                    'action': command['action'],
                    'raw_text': text
                }
        
        return None
    
    def parse_brightness(self, text: str) -> Optional[float]:
        """
        解析亮度值
        
        例如: "亮度调到50" -> 0.5
        
        Returns:
            0.0 ~ 1.0 的亮度值，或 None
        """
        import re
        
        # 尝试匹配数字
        patterns = [
            r'(\d+)%',           # 50%
            r'亮度.*?(\d+)',      # 亮度50
            r'调到.*?(\d+)',      # 调到50
            r'设为.*?(\d+)',      # 设为50
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = int(match.group(1))
                return max(0.0, min(1.0, value / 100.0))
        
        return None
    
    def is_wake_word(self, text: str, wake_words: List[str] = None) -> bool:
        """
        检查是否包含唤醒词
        
        Args:
            text: 文本
            wake_words: 唤醒词列表
            
        Returns:
            是否包含唤醒词
        """
        if wake_words is None:
            wake_words = ['小灯', '台灯', '灯灯']
        
        for word in wake_words:
            if word in text:
                return True
        
        return False
