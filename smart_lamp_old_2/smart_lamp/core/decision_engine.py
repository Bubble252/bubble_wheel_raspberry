"""
决策引擎 - 根据事件决定执行的动作
"""
from typing import Dict, List, Optional, Any
from .message_bus import Message, MessageType
from .state_machine import StateMachine, LampState


class DecisionEngine:
    """
    决策引擎
    根据传感器输入和当前状态，决定执行什么动作
    """
    
    def __init__(self, config: dict):
        """
        初始化决策引擎
        
        Args:
            config: 配置字典
        """
        self.config = config
        self.current_brightness = config.get('defaults', {}).get('brightness', 0.5)
        
        # 从配置加载映射
        self.emotion_mapping = config.get('emotion_mapping', {})
        self.voice_commands = config.get('voice_commands', {})
        
        # 默认映射（如果配置中没有）
        if not self.emotion_mapping:
            self.emotion_mapping = {
                'Happy': {'action': 'cute', 'brightness': 0.8},
                'Sad': {'action': 'nod_slow', 'brightness': 0.4},
                'Angry': {'action': 'shake', 'brightness': 0.3},
                'Surprise': {'action': 'nod', 'brightness': 0.9},
                'Neutral': {'action': None, 'brightness': None},
                'Fear': {'action': 'shake', 'brightness': 0.5},
                'Disgust': {'action': None, 'brightness': 0.5},
            }
        
        if not self.voice_commands:
            self.voice_commands = {
                '开灯': {'brightness': 0.8},
                '关灯': {'brightness': 0.0},
                '亮一点': {'brightness_delta': 0.2},
                '暗一点': {'brightness_delta': -0.2},
                '最亮': {'brightness': 1.0},
                '蹦迪': {'action': 'dance'},
                '点头': {'action': 'nod'},
                '摇头': {'action': 'shake'},
                '卖萌': {'action': 'cute'},
                '打招呼': {'action': 'wave'},
                '休息': {'action': 'sleep'},
            }
        
        # 手势映射
        self.gesture_mapping = {
            'thumbs_up': {'brightness_delta': 0.2},       # 点赞 -> 亮一点
            'thumbs_down': {'brightness_delta': -0.2},   # 倒赞 -> 暗一点
            'open_palm': {'brightness': 1.0},            # 手掌 -> 最亮
            'fist': {'brightness': 0.0},                 # 握拳 -> 关灯
            'wave': {'action': 'wave'},                  # 挥手 -> 打招呼
        }
        
        # 上次检测到的情绪（防止重复触发）
        self._last_emotion = None
        self._emotion_stable_count = 0
        self._emotion_threshold = 3  # 连续检测到相同情绪才触发
    
    def process(self, message: Message, state_machine: StateMachine = None) -> List[Message]:
        """
        处理消息，返回要执行的动作列表
        
        Args:
            message: 输入消息
            state_machine: 状态机（可选，用于状态相关决策）
            
        Returns:
            要执行的动作消息列表
        """
        actions = []
        
        if message.type == MessageType.EMOTION_CHANGED:
            actions = self._process_emotion(message.data)
            
        elif message.type == MessageType.VOICE_COMMAND:
            actions = self._process_voice_command(message.data)
            
        elif message.type == MessageType.GESTURE_DETECTED:
            actions = self._process_gesture(message.data)
            
        elif message.type == MessageType.FACE_DETECTED:
            # 检测到人脸，可以触发打招呼
            if message.data.get('is_new', False):
                actions.append(Message(
                    type=MessageType.PLAY_ACTION,
                    data='wave',
                    source='decision_engine'
                ))
                
        elif message.type == MessageType.FACE_LOST:
            # 人脸丢失，进入空闲
            pass
        
        return actions
    
    def _process_emotion(self, data: dict) -> List[Message]:
        """处理情绪事件"""
        actions = []
        emotion = data.get('emotion', '')
        confidence = data.get('confidence', 0)
        
        # 置信度过滤
        if confidence < 0.5:
            return actions
        
        # 稳定性检测：连续多次相同情绪才触发
        if emotion == self._last_emotion:
            self._emotion_stable_count += 1
        else:
            self._last_emotion = emotion
            self._emotion_stable_count = 1
        
        # 只有稳定后才触发
        if self._emotion_stable_count < self._emotion_threshold:
            return actions
        
        # 获取映射
        mapping = self.emotion_mapping.get(emotion, {})
        
        if mapping.get('action'):
            actions.append(Message(
                type=MessageType.PLAY_ACTION,
                data=mapping['action'],
                source='decision_engine'
            ))
        
        if mapping.get('brightness') is not None:
            self.current_brightness = mapping['brightness']
            actions.append(Message(
                type=MessageType.SET_BRIGHTNESS,
                data=self.current_brightness,
                source='decision_engine'
            ))
        
        # 重置计数器，防止持续触发
        self._emotion_stable_count = 0
        
        return actions
    
    def _process_voice_command(self, data: dict) -> List[Message]:
        """处理语音命令"""
        actions = []
        text = data.get('text', '')
        command = data.get('command', text)  # 如果有解析后的命令就用，否则用原文
        
        # 查找匹配的命令
        mapping = None
        for cmd_key, cmd_mapping in self.voice_commands.items():
            if cmd_key in command or cmd_key in text:
                mapping = cmd_mapping
                break
        
        if mapping is None:
            return actions
        
        # 绝对亮度
        if 'brightness' in mapping:
            self.current_brightness = mapping['brightness']
            actions.append(Message(
                type=MessageType.SET_BRIGHTNESS,
                data=self.current_brightness,
                source='decision_engine'
            ))
        
        # 相对亮度
        if 'brightness_delta' in mapping:
            self.current_brightness = max(0.0, min(1.0, 
                self.current_brightness + mapping['brightness_delta']))
            actions.append(Message(
                type=MessageType.SET_BRIGHTNESS,
                data=self.current_brightness,
                source='decision_engine'
            ))
        
        # 动作
        if 'action' in mapping:
            actions.append(Message(
                type=MessageType.PLAY_ACTION,
                data=mapping['action'],
                source='decision_engine'
            ))
        
        return actions
    
    def _process_gesture(self, data: dict) -> List[Message]:
        """处理手势事件"""
        actions = []
        gesture = data.get('gesture', '')
        
        mapping = self.gesture_mapping.get(gesture, {})
        
        if 'brightness' in mapping:
            self.current_brightness = mapping['brightness']
            actions.append(Message(
                type=MessageType.SET_BRIGHTNESS,
                data=self.current_brightness,
                source='decision_engine'
            ))
        
        if 'brightness_delta' in mapping:
            self.current_brightness = max(0.0, min(1.0,
                self.current_brightness + mapping['brightness_delta']))
            actions.append(Message(
                type=MessageType.SET_BRIGHTNESS,
                data=self.current_brightness,
                source='decision_engine'
            ))
        
        if 'action' in mapping:
            actions.append(Message(
                type=MessageType.PLAY_ACTION,
                data=mapping['action'],
                source='decision_engine'
            ))
        
        return actions
    
    def get_brightness(self) -> float:
        """获取当前亮度"""
        return self.current_brightness
    
    def set_brightness(self, value: float):
        """设置亮度"""
        self.current_brightness = max(0.0, min(1.0, value))
