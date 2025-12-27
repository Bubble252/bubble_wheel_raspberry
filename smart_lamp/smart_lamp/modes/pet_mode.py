"""
桌宠模式
监听语音命令，执行各种表情动作
"""
import random
import time
from typing import Dict, List, Optional
from .base_mode import BaseMode


class PetMode(BaseMode):
    """
    桌宠模式
    
    功能：
    - 监听语音动作指令（卖萌、跳舞、兴奋等）
    - 执行预设的舵机动作序列
    - 支持随机待机动作
    - 可以播放音效（如果有音频输出）
    """
    
    MODE_NAME = "桌宠"
    
    # 动作命令映射
    ACTION_COMMANDS = {
        # 命令关键词 -> 动作名称
        '卖萌': 'cute',
        '可爱': 'cute',
        '撒娇': 'cute',
        '跳舞': 'dance',
        '蹦迪': 'dance',
        '兴奋': 'excited',
        '开心': 'happy',
        '高兴': 'happy',
        '点头': 'nod',
        '摇头': 'shake',
        '打招呼': 'wave',
        '招手': 'wave',
        '害羞': 'shy',
        '生气': 'angry',
        '睡觉': 'sleep',
        '休息': 'sleep',
        '醒来': 'wakeup',
        '起来': 'wakeup',
    }
    
    def __init__(self, controller):
        super().__init__(controller)
        
        # 当前播放的动作
        self._current_action: Optional[str] = None
        self._action_start_time: float = 0
        
        # 待机动作配置
        self._idle_interval = 10.0  # 待机多少秒后随机动作
        self._last_activity_time = time.time()
        self._idle_actions = ['cute', 'nod', 'shake']  # 待机时随机播放的动作
        
        # 动作状态
        self._is_playing = False
    
    def on_enter(self):
        """进入模式：打招呼"""
        self._last_activity_time = time.time()
        self._print("我是你的桌宠！试试说：卖萌、跳舞、点头...")
        
        # 进入时打招呼
        self._play_action('wave')
    
    def on_exit(self):
        """退出模式：告别动作"""
        # 立即停止所有播放（音乐/语音循环）
        if self.controller:
            speaker = getattr(self.controller, '_speaker', None)
            if speaker:
                speaker.stop_immediately()  # 立即停止，不通过队列
        
        self._play_action('sleep')
        self._print("桌宠休息了~")
    
    def update(self, frame=None, voice_text: str = None) -> bool:
        """
        更新模式
        
        Returns:
            是否继续运行
        """
        # 处理语音命令
        if voice_text:
            if self.handle_voice(voice_text):
                self._last_activity_time = time.time()
        
        # 检查待机随机动作
        self._check_idle_action()
        
        return True
    
    def handle_voice(self, text: str) -> bool:
        """
        处理语音命令
        
        Args:
            text: 语音识别文本
            
        Returns:
            是否处理了该命令
        """
        text = text.strip()
        
        # 查找匹配的动作命令
        for keyword, action in self.ACTION_COMMANDS.items():
            if keyword in text:
                self._print(f"收到指令: {keyword} -> 执行动作: {action}")
                self._play_action(action)
                return True
        
        # 特殊命令
        if '停' in text or '别动' in text:
            self._stop_action()
            self._print("好的，我不动了~")
            return True
        
        if '随便' in text or '随机' in text:
            action = random.choice(list(set(self.ACTION_COMMANDS.values())))
            self._print(f"随机动作: {action}")
            self._play_action(action)
            return True
        
        return False
    
    def _play_action(self, action_name: str):
        """
        播放动作
        
        Args:
            action_name: 动作名称（对应 actions.yaml 中的定义）
        """
        self._current_action = action_name
        self._action_start_time = time.time()
        self._is_playing = True
        
        # 调用舵机线程播放动作
        if self.controller:
            servo_thread = getattr(self.controller, '_servo_thread', None)
            if servo_thread:
                servo_thread.play_action(action_name)
                self._debug(f"播放动作: {action_name}")
            else:
                self._print(f"[模拟] 播放动作: {action_name}")
            
            # 先立即停止之前的循环播放（重要！切换动作时必须先停止）
            speaker = getattr(self.controller, '_speaker', None)
            if speaker:
                speaker.stop_immediately()  # 立即停止，不通过队列
                
                # 根据动作类型启动新的语音反馈
                if action_name == 'nod':
                    # 点头：每1.5秒说"牛逼"
                    speaker.start_nod_voice("牛逼", 1.5)
                elif action_name == 'dance':
                    # 跳舞：循环随机播放音乐
                    speaker.start_dance_music()
    
    def _stop_action(self):
        """停止当前动作"""
        self._is_playing = False
        self._current_action = None
        
        if self.controller:
            servo_thread = getattr(self.controller, '_servo_thread', None)
            if servo_thread:
                servo_thread.stop_action()
            
            # 立即停止语音循环
            speaker = getattr(self.controller, '_speaker', None)
            if speaker:
                speaker.stop_immediately()
    
    def _check_idle_action(self):
        """检查是否需要播放待机随机动作"""
        if self._is_playing:
            return
        
        idle_time = time.time() - self._last_activity_time
        
        if idle_time > self._idle_interval:
            # 随机播放一个待机动作
            action = random.choice(self._idle_actions)
            self._debug(f"待机随机动作: {action}")
            self._play_action(action)
            self._last_activity_time = time.time()
    
    def get_available_commands(self) -> List[str]:
        """获取可用的命令列表"""
        return list(self.ACTION_COMMANDS.keys())


# ==================== 独立测试 ====================
def test_pet_mode():
    """独立测试桌宠模式"""
    print("=" * 50)
    print("桌宠模式 - 独立测试")
    print("=" * 50)
    print()
    print("可用命令:", list(PetMode.ACTION_COMMANDS.keys()))
    print()
    print("输入命令测试，输入 'q' 退出")
    print("-" * 50)
    
    # 创建模拟控制器
    class MockController:
        def __init__(self):
            self.debug = True
            self._servo_thread = None
    
    controller = MockController()
    mode = PetMode(controller)
    
    # 进入模式
    mode.enter()
    
    try:
        while True:
            # 模拟语音输入
            text = input("\n请输入命令 (q退出): ").strip()
            
            if text.lower() == 'q':
                break
            
            if text:
                if mode.handle_voice(text):
                    print("  ✓ 命令已处理")
                else:
                    print("  ✗ 未识别的命令")
            
            # 更新模式
            mode.update()
            
    finally:
        mode.exit()
        print("\n测试结束")


if __name__ == "__main__":
    test_pet_mode()
