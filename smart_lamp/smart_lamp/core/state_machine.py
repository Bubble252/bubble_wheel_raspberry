"""
状态机 - 管理台灯系统的运行状态
重构版：清晰的模式切换架构
"""
import time
from enum import Enum, auto
from typing import Callable, Optional, List


class LampState(Enum):
    """
    台灯状态枚举
    
    状态流转:
    
    STANDBY (待机)
        │
        └─ 唤醒词"宝莉" ──► LISTENING (监听)
                               │
                               ├─ "手部跟随" ──► HAND_FOLLOW
                               ├─ "桌宠模式" ──► PET_MODE  
                               ├─ "亮度调节" ──► BRIGHTNESS_MODE
                               │
                               └─ 超时 ──► STANDBY
    
    任意模式:
        ├─ "退出" ──► STANDBY
        └─ "切换到XX" ──► 对应模式
    """
    
    # === 基础状态 ===
    STANDBY = auto()         # 待机：等待唤醒词
    LISTENING = auto()       # 监听：等待模式切换指令
    
    # === 功能模式 ===
    HAND_FOLLOW = auto()     # 手部跟随模式
    PET_MODE = auto()        # 桌宠模式
    BRIGHTNESS_MODE = auto() # 亮度调节模式
    
    # === 系统状态 ===
    ERROR = auto()           # 错误状态


# 模式名称映射（用于语音识别，包含同音词）
MODE_NAMES = {
    LampState.HAND_FOLLOW: [
        '手部跟随', '跟随模式', '跟随',
        '手不跟随', '手步跟随',  # 同音词
        '跟着我', '跟踪',
    ],
    LampState.PET_MODE: [
        '桌宠模式', '桌宠', '宠物模式','捉虫模式','捉虫',
        '卓宠', '座宠', '做宠',  # 同音词
        '互动模式', '陪我玩',
    ],
    LampState.BRIGHTNESS_MODE: [
        '亮度调节', '亮度模式', '调节亮度',
        '量度调节', '量度模式',  # 同音词
        '调灯', '调亮度',
    ],
}

# 反向映射：名称 -> 状态
NAME_TO_MODE = {}
for state, names in MODE_NAMES.items():
    for name in names:
        NAME_TO_MODE[name] = state


class StateMachine:
    """
    状态机
    管理状态转换、超时检测、状态回调
    """
    
    def __init__(self):
        self._state = LampState.STANDBY
        self._state_enter_time = time.time()
        self._callbacks: List[Callable] = []
        self._previous_state: Optional[LampState] = None
        
        # 超时配置（秒）
        self.listening_timeout = 10.0  # 监听模式超时
        
    @property
    def state(self) -> LampState:
        """当前状态"""
        return self._state
    
    @property
    def previous_state(self) -> Optional[LampState]:
        """上一个状态"""
        return self._previous_state
    
    @property
    def state_duration(self) -> float:
        """当前状态持续时间（秒）"""
        return time.time() - self._state_enter_time
    
    @property
    def is_in_mode(self) -> bool:
        """是否处于某个功能模式中"""
        return self._state in [
            LampState.HAND_FOLLOW,
            LampState.PET_MODE,
            LampState.BRIGHTNESS_MODE
        ]
    
    @property
    def mode_name(self) -> str:
        """当前模式的中文名称"""
        names = {
            LampState.STANDBY: '待机',
            LampState.LISTENING: '监听',
            LampState.HAND_FOLLOW: '手部跟随',
            LampState.PET_MODE: '桌宠',
            LampState.BRIGHTNESS_MODE: '亮度调节',
            LampState.ERROR: '错误',
        }
        return names.get(self._state, '未知')
    
    def transition_to(self, new_state: LampState) -> bool:
        """
        状态转换
        
        Args:
            new_state: 目标状态
            
        Returns:
            是否转换成功
        """
        if new_state == self._state:
            return False
        
        old_state = self._state
        self._previous_state = old_state
        self._state = new_state
        self._state_enter_time = time.time()
        
        # 触发回调
        for callback in self._callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                print(f"[StateMachine] 回调执行失败: {e}")
        
        return True
    
    def on_change(self, callback: Callable[[LampState, LampState], None]):
        """
        注册状态变化回调
        
        Args:
            callback: 回调函数，参数为 (old_state, new_state)
        """
        if callback not in self._callbacks:
            self._callbacks.append(callback)
    
    def check_timeout(self) -> bool:
        """
        检查是否超时
        
        Returns:
            是否触发了超时转换
        """
        # 监听状态超时 -> 回到待机
        if self._state == LampState.LISTENING:
            if self.state_duration > self.listening_timeout:
                self.transition_to(LampState.STANDBY)
                return True
        
        return False
    
    def get_available_modes(self) -> List[str]:
        """获取可用的模式名称列表"""
        return list(NAME_TO_MODE.keys())
    
    def parse_mode_command(self, text: str) -> Optional[LampState]:
        """
        解析模式切换命令
        
        Args:
            text: 语音识别文本
            
        Returns:
            目标模式，如果没有匹配则返回 None
        """
        text = text.strip()
        
        # 直接匹配模式名
        if text in NAME_TO_MODE:
            return NAME_TO_MODE[text]
        
        # 模糊匹配："切换到XX"、"进入XX"
        for prefix in ['切换到', '进入', '打开', '启动']:
            if text.startswith(prefix):
                mode_name = text[len(prefix):]
                if mode_name in NAME_TO_MODE:
                    return NAME_TO_MODE[mode_name]
        
        # 包含匹配
        for name, mode in NAME_TO_MODE.items():
            if name in text:
                return mode
        
        return None
    
    def is_exit_command(self, text: str) -> bool:
        """检查是否是退出命令（包含同音词）"""
        exit_words = [
            '退出', '结束', '关闭', '停止', '返回待机', '返回',
            '退去', '推出',  # 同音词
        ]
        return any(word in text for word in exit_words)
    
    def __str__(self) -> str:
        return f"StateMachine(state={self._state.name}, duration={self.state_duration:.1f}s)"
    
    def __repr__(self) -> str:
        return self.__str__()
