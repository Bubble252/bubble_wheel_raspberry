"""
主控制器 - 系统调度中心
重构版：清晰的模式切换架构
"""
import signal
import threading
import time
from typing import Optional, Dict, Type
from enum import Enum

from .state_machine import StateMachine, LampState, NAME_TO_MODE
from ..modes.base_mode import BaseMode
from ..modes.hand_follow_mode import HandFollowMode
from ..modes.pet_mode import PetMode
from ..modes.brightness_mode import BrightnessMode
from ..utils.logger import get_logger
from ..utils.config_loader import load_config


class MainController:
    """
    主控制器
    
    职责：
    1. 管理系统生命周期
    2. 处理唤醒词和模式切换
    3. 调度各功能模式
    4. 协调硬件模块
    
    状态流转：
    STANDBY -> (唤醒词) -> LISTENING -> (模式命令) -> 功能模式
    功能模式 -> ("退出") -> STANDBY
    功能模式 -> ("切换到XX") -> 其他功能模式
    """
    
    # 唤醒词（包含同音词）
    WAKE_WORDS = ["宝莉", "保利", "包里", "宝利", "保丽", "抱你","报理","暴力","暴利","宝力"]
    
    # 模式类映射
    MODE_CLASSES: Dict[LampState, Type[BaseMode]] = {
        LampState.HAND_FOLLOW: HandFollowMode,
        LampState.PET_MODE: PetMode,
        LampState.BRIGHTNESS_MODE: BrightnessMode,
    }
    
    def __init__(self, config_path: str = "config/config.yaml"):
        """
        初始化主控制器
        
        Args:
            config_path: 配置文件路径
        """
        self.logger = get_logger("MainController")
        self._print("=" * 50)
        self._print("智能台灯系统 - 初始化")
        self._print("=" * 50)
        
        # 加载配置
        self.config = load_config(config_path)
        self.debug = self.config.get('debug', False)
        
        # 状态机
        self.state_machine = StateMachine()
        self.state_machine.on_change(self._on_state_changed)
        
        # 当前活跃的功能模式
        self._current_mode: Optional[BaseMode] = None
        
        # 硬件模块（稍后初始化）
        self._camera = None
        self._voice = None
        self._servo_thread = None
        self._lighting = None
        
        # 运行状态
        self._running = False
        
        # 模拟选项
        self.simulate_servo = False  # 舵机只打印不执行
        self.disable_voice = False   # 禁用语音
        
        # 配置超时时间
        self.state_machine.listening_timeout = self.config.get(
            'listening_timeout', 10.0
        )
        
        self._print(f"唤醒词: {self.WAKE_WORDS[0]} (含同音词)")
        self._print(f"监听超时: {self.state_machine.listening_timeout}秒")
    
    def _print(self, message: str, level: str = "INFO"):
        """格式化打印"""
        timestamp = time.strftime("%H:%M:%S")
        prefix = {
            "INFO": "ℹ",
            "WARN": "⚠",
            "ERROR": "✗",
            "SUCCESS": "✓",
            "MODE": "🎮",
        }.get(level, "•")
        print(f"[{timestamp}] {prefix} {message}")
    
    def _debug(self, message: str):
        """调试打印"""
        if self.debug:
            timestamp = time.strftime("%H:%M:%S")
            print(f"[{timestamp}] [DEBUG] {message}")
    
    # ==================== 生命周期 ====================
    
    def start(self):
        """启动系统"""
        if self._running:
            self._print("系统已在运行", "WARN")
            return
        
        self._print("启动系统...")
        self._running = True
        
        # 初始化硬件模块
        self._init_hardware()
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self._print("系统启动完成", "SUCCESS")
        self._print("-" * 50)
        self._print(f"说 \"{self.WAKE_WORDS[0]}\" 唤醒我")
        self._print("-" * 50)
    
    def stop(self):
        """停止系统"""
        self._print("停止系统...")
        self._running = False
        
        # 退出当前模式
        if self._current_mode:
            self._current_mode.exit()
            self._current_mode = None
        
        # 停止硬件模块
        self._stop_hardware()
        
        self._print("系统已停止", "SUCCESS")
    
    def _signal_handler(self, signum, frame):
        """信号处理"""
        self._print(f"收到信号 {signum}，准备退出...", "WARN")
        self.stop()
    
    @property
    def running(self) -> bool:
        """是否运行中"""
        return self._running
    
    # ==================== 硬件初始化 ====================
    
    def _init_hardware(self):
        """初始化硬件模块"""
        module_config = self.config.get('modules', {})
        
        # 初始化摄像头
        if module_config.get('vision', {}).get('enabled', True):
            try:
                from ..modules.vision import Camera
                camera_config = self.config.get('devices', {}).get('camera', {})
                self._camera = Camera(
                    device_id=camera_config.get('device_id', 0),
                    width=camera_config.get('width', 640),
                    height=camera_config.get('height', 480)
                )
                if self._camera.open():
                    self._print("摄像头初始化成功", "SUCCESS")
                else:
                    self._print("摄像头打开失败", "ERROR")
                    self._camera = None
            except Exception as e:
                self._print(f"摄像头初始化失败: {e}", "ERROR")
        
        # 初始化语音
        if not self.disable_voice and module_config.get('voice', {}).get('enabled', True):
            try:
                from ..modules.voice import VoiceThread
                self._voice = VoiceThread(self.config)
                self._voice.start()
                self._print("语音模块初始化成功", "SUCCESS")
            except Exception as e:
                self._print(f"语音模块初始化失败: {e}", "ERROR")
        elif self.disable_voice:
            self._print("语音模块已禁用", "WARN")
        
        # 初始化舵机
        if not self.simulate_servo and module_config.get('servo', {}).get('enabled', True):
            try:
                from ..modules.servo import ServoThread
                servo_config = self.config.get('servo', {})
                self._print(f"[DEBUG] 舵机配置: {servo_config}")
                self._servo_thread = ServoThread(servo_config)
                self._servo_thread.start()
                self._print(f"[DEBUG] 舵机线程已启动: {self._servo_thread}")
                self._print(f"[DEBUG] 舵机线程 is_alive: {self._servo_thread.is_alive()}")
                self._print("舵机模块初始化成功", "SUCCESS")
            except Exception as e:
                self._print(f"舵机模块初始化失败: {e}", "ERROR")
                import traceback
                traceback.print_exc()
        elif self.simulate_servo:
            # 创建模拟舵机
            self._servo_thread = MockServoThread()
            self._print("舵机模块[模拟]", "WARN")
        
        # 初始化照明
        if module_config.get('lighting', {}).get('enabled', True):
            try:
                from ..modules.lighting import BrightnessController
                self._lighting = BrightnessController(self.config.get('stm32', {}))
                if self._lighting.connect():
                    self._print("照明模块初始化成功", "SUCCESS")
                else:
                    self._print("照明模块连接失败", "WARN")
            except Exception as e:
                self._print(f"照明模块初始化失败: {e}", "ERROR")
    
    def _stop_hardware(self):
        """停止硬件模块"""
        if self._camera:
            self._camera.close()
        
        if self._voice:
            self._voice.stop()
        
        if self._servo_thread:
            self._servo_thread.stop()
        
        if self._lighting:
            self._lighting.disconnect()
    
    # ==================== 主循环 ====================
    
    def update(self):
        """
        主循环更新（由 run.py 调用）
        """
        if not self._running:
            return
        
        # 获取输入
        frame = self._get_frame()
        voice_text = self._get_voice_text()
        
        # 处理语音（全局命令）
        if voice_text:
            self._handle_global_voice(voice_text)
        
        # 检查超时
        self.state_machine.check_timeout()
        
        # 根据状态处理
        state = self.state_machine.state
        
        if state == LampState.STANDBY:
            # 待机：只等待唤醒词
            pass
        
        elif state == LampState.LISTENING:
            # 监听：等待模式切换命令
            if voice_text:
                self._handle_mode_command(voice_text)
        
        elif self.state_machine.is_in_mode:
            # 功能模式中：更新当前模式
            if self._current_mode:
                # 传递语音命令给模式
                if voice_text:
                    self._current_mode.handle_voice(voice_text)
                
                # 更新模式
                should_continue = self._current_mode.update(
                    frame=frame,
                    voice_text=voice_text
                )
                
                if not should_continue:
                    self._exit_current_mode()
        
        # 小延迟，避免 CPU 占用过高
        time.sleep(0.01)
    
    def _get_frame(self):
        """获取摄像头帧"""
        if self._camera:
            return self._camera.read()
        return None
    
    def _get_voice_text(self) -> Optional[str]:
        """获取语音识别文本"""
        if self._voice:
            return self._voice.get_text()
        return None
    
    # ==================== 语音处理 ====================
    
    def _handle_global_voice(self, text: str):
        """
        处理全局语音命令（任何状态下都响应）
        
        Args:
            text: 语音识别文本
        """
        self._debug(f"语音输入: {text}")
        
        state = self.state_machine.state
        
        # 待机状态：检测唤醒词（包含同音词）
        if state == LampState.STANDBY:
            for wake_word in self.WAKE_WORDS:
                if wake_word in text:
                    self._print(f"唤醒词检测到: {wake_word}", "SUCCESS")
                    self.state_machine.transition_to(LampState.LISTENING)
                    self._print("请说模式名称：手部跟随、桌宠模式、亮度调节")
                    # TODO: 播放提示音
                    return
            return
        
        # 任何模式下：检测退出命令
        if self.state_machine.is_exit_command(text):
            self._print("收到退出命令", "MODE")
            self._exit_current_mode()
            return
        
        # 任何模式下：检测切换命令
        target_mode = self.state_machine.parse_mode_command(text)
        if target_mode and target_mode != state:
            self._print(f"切换到: {target_mode.name}", "MODE")
            self._switch_to_mode(target_mode)
            return
    
    def _handle_mode_command(self, text: str):
        """
        处理模式切换命令（监听状态）
        
        Args:
            text: 语音识别文本
        """
        target_mode = self.state_machine.parse_mode_command(text)
        
        if target_mode:
            self._switch_to_mode(target_mode)
        else:
            self._print(f"未识别的命令: {text}", "WARN")
            self._print("可用模式: 手部跟随、桌宠模式、亮度调节")
    
    # ==================== 模式管理 ====================
    
    def _switch_to_mode(self, target_state: LampState):
        """
        切换到指定模式
        
        Args:
            target_state: 目标状态
        """
        self._print(f"[DEBUG] _switch_to_mode: target={target_state}")
        
        # 退出当前模式
        if self._current_mode:
            self._current_mode.exit()
            self._current_mode = None
        
        # 创建新模式
        mode_class = self.MODE_CLASSES.get(target_state)
        if mode_class:
            self._print(f"[DEBUG] 创建模式实例: {mode_class}")
            self._current_mode = mode_class(self)
            
            # 初始化舵机（延迟初始化，进入模式时才通信）
            self._print(f"[DEBUG] _servo_thread = {self._servo_thread}")
            if self._servo_thread:
                self._print(f"[DEBUG] 调用 servo_thread.init()")
                self._servo_thread.init()
            else:
                self._print(f"[DEBUG] 警告: _servo_thread 为 None!")
            
            self._current_mode.enter()
            self.state_machine.transition_to(target_state)
        else:
            self._print(f"未知模式: {target_state}", "ERROR")
            self.state_machine.transition_to(LampState.STANDBY)
    
    def _exit_current_mode(self):
        """退出当前模式，返回待机"""
        if self._current_mode:
            self._current_mode.exit()
            self._current_mode = None
        
        # 暂停舵机通信（让出 USB 带宽给语音识别）
        if self._servo_thread:
            self._servo_thread.suspend()
        
        self.state_machine.transition_to(LampState.STANDBY)
        self._print("-" * 50)
        self._print(f"已返回待机，说 \"{self.WAKE_WORDS[0]}\" 唤醒")
        self._print("-" * 50)
    
    # ==================== 状态回调 ====================
    
    def _on_state_changed(self, old_state: LampState, new_state: LampState):
        """状态变化回调"""
        self._print(f"状态: {old_state.name} -> {new_state.name}", "MODE")


# ==================== 独立测试 ====================
def test_main_controller():
    """测试主控制器（模拟模式）"""
    print("=" * 50)
    print("主控制器 - 模拟测试")
    print("=" * 50)
    print()
    print("模拟语音输入，测试状态流转")
    print("输入 'q' 退出测试")
    print("-" * 50)
    
    # 创建简化的控制器（不初始化硬件）
    class MockMainController(MainController):
        def _init_hardware(self):
            self._print("跳过硬件初始化（模拟模式）")
        
        def _stop_hardware(self):
            pass
    
    controller = MockMainController.__new__(MockMainController)
    controller.logger = None
    controller.config = {'debug': True}
    controller.debug = True
    controller.state_machine = StateMachine()
    controller.state_machine.on_change(controller._on_state_changed)
    controller._current_mode = None
    controller._camera = None
    controller._voice = None
    controller._servo_thread = None
    controller._lighting = None
    controller._running = True
    
    controller._print("模拟控制器已启动")
    controller._print(f"唤醒词: {controller.WAKE_WORDS[0]}")
    controller._print("-" * 50)
    
    try:
        while controller._running:
            # 模拟语音输入
            text = input(f"\n[{controller.state_machine.state.name}] 输入语音 (q退出): ").strip()
            
            if text.lower() == 'q':
                break
            
            if text:
                controller._handle_global_voice(text)
                
                # 如果在监听状态，也尝试处理模式命令
                if controller.state_machine.state == LampState.LISTENING:
                    controller._handle_mode_command(text)
            
            # 检查超时
            if controller.state_machine.check_timeout():
                controller._print("监听超时，返回待机")
                
    finally:
        controller.stop()
        print("\n测试结束")


# ==================== 模拟类 ====================

class MockServoThread:
    """
    模拟舵机线程
    只打印动作，不真正执行
    """
    
    def __init__(self):
        self._current_positions = {1: 512, 2: 512, 3: 512}
        self._is_playing = False
        self._is_locked = False
    
    def start(self):
        print("[MockServo] 模拟舵机线程启动")
    
    def stop(self):
        print("[MockServo] 模拟舵机线程停止")
    
    def play_action(self, action_name: str):
        print(f"[MockServo] 🎬 播放动作: {action_name}")
        self._is_playing = True
    
    def stop_action(self):
        print("[MockServo] ⏹ 停止动作")
        self._is_playing = False
    
    def move(self, servo_id: int, position: int, speed: int = 500):
        print(f"[MockServo] 移动舵机{servo_id} -> {position} (速度:{speed})")
        self._current_positions[servo_id] = position
    
    def sync_move(self, positions: dict, speed: int = 500):
        pos_str = ", ".join([f"S{k}:{v}" for k, v in positions.items()])
        print(f"[MockServo] 同步移动: {pos_str} (速度:{speed})")
        self._current_positions.update(positions)
    
    def home(self):
        print("[MockServo] 🏠 回到初始位置")
        self._current_positions = {1: 512, 2: 512, 3: 512}
    
    def hold_position(self):
        print("[MockServo] 🔒 锁定位置")
        self._is_locked = True
    
    def release_position(self):
        print("[MockServo] 🔓 解锁位置")
        self._is_locked = False
    
    def get_positions(self) -> dict:
        return self._current_positions.copy()
    
    @property
    def is_playing(self) -> bool:
        return self._is_playing
    
    @property
    def is_locked(self) -> bool:
        return self._is_locked


if __name__ == "__main__":
    test_main_controller()
