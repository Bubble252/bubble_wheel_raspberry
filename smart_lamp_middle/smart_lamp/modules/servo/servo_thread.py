"""
舵机控制线程
简化版：接收控制命令，驱动舵机执行动作
"""
import threading
import time
from typing import Optional, Dict
from queue import Queue, Empty

from .servo_driver import ServoDriver
from .action_player import ActionPlayer


class ServoThread(threading.Thread):
    """
    舵机控制线程
    
    功能：
    - 连接舵机
    - 执行移动命令
    - 播放预设动作
    - 支持位置锁定
    """
    
    def __init__(self, config: dict):
        """
        初始化舵机线程
        
        Args:
            config: 舵机配置字典
        """
        print("[ServoThread] __init__ 开始")
        super().__init__(daemon=True, name="ServoThread")
        print("[ServoThread] super().__init__ 完成")
        
        self.config = config
        self._running = False
        
        # 初始化舵机驱动（从config提取port和baudrate）
        port = config.get('port', '/dev/ttyUSB0')
        baudrate = config.get('baudrate', 1000000)
        print(f"[ServoThread] 创建 ServoDriver: port={port}, baudrate={baudrate}")
        self.driver = ServoDriver(port, baudrate)
        print("[ServoThread] ServoDriver 创建完成")
        
        # 舵机ID列表
        self.servo_ids = config.get('servo_ids', [1, 2, 3])
        
        # 动作播放器
        actions_file = config.get('actions_file', 'config/actions.yaml')
        print(f"[ServoThread] 创建 ActionPlayer: {actions_file}")
        self.action_player = ActionPlayer(self.driver, actions_file)
        print("[ServoThread] ActionPlayer 创建完成")
        
        # 命令队列
        self._command_queue: Queue = Queue()
        
        # 当前位置缓存
        self._current_positions: Dict[int, int] = {}
        
        # 位置锁定标志
        self._position_locked = False
        
        # 延迟初始化标志（注意：不能用 _initialized，会和 threading.Thread 冲突！）
        self._servo_initialized = False
        self._suspended = False  # 暂停通信（用于退出模式时）
        print("[ServoThread] __init__ 完成")
    
    def run(self):
        """线程主循环"""
        self._print("舵机线程启动")
        self._running = True
        
        # 连接舵机（只打开串口，不通信）
        if not self.driver.connect():
            self._print("舵机连接失败")
            return
        
        self._print("舵机已连接，等待初始化命令...")
        
        # 主循环
        while self._running:
            try:
                cmd = self._command_queue.get(timeout=0.1)
                self._handle_command(cmd)
            except Empty:
                pass
            except Exception as e:
                self._print(f"命令处理错误: {e}")
        
        # 清理
        self.action_player.stop()
        self._home()
        self.driver.disconnect()
        
        self._print("舵机线程退出")
    
    def _handle_command(self, cmd: Dict):
        """处理命令"""
        cmd_type = cmd.get('type')
        self._print(f"[DEBUG] 收到命令: {cmd_type}, suspended={self._suspended}, initialized={self._servo_initialized}")
        
        # === 初始化命令（延迟初始化） ===
        if cmd_type == 'init':
            self._print(f"[DEBUG] init 命令: 当前 suspended={self._suspended}")
            if not self._servo_initialized:
                self._do_init()
            self._suspended = False  # 强制恢复通信
            self._print(f"[DEBUG] init 命令完成: suspended={self._suspended}")
            return
        
        # === 暂停/恢复通信 ===
        if cmd_type == 'suspend':
            self._suspended = True
            self._print("舵机通信已暂停")
            return
        
        if cmd_type == 'resume':
            self._suspended = False
            self._print("舵机通信已恢复")
            return
        
        # 暂停状态下忽略其他命令
        if self._suspended:
            self._print(f"[DEBUG] 命令 {cmd_type} 被忽略: suspended=True")
            return
        
        # 未初始化时忽略需要预设动作的命令（move/sync_move 不受限制，因为 connect 已完成）
        if not self._servo_initialized and cmd_type in ['play_action', 'home']:
            return
        
        if cmd_type == 'play_action':
            if not self._position_locked:
                action_name = cmd.get('action')
                if action_name:
                    self._print(f"播放: {action_name}")
                    self.action_player.play(action_name)
                
        elif cmd_type == 'stop_action':
            self.action_player.stop()
            
        elif cmd_type == 'move':
            if not self._position_locked:
                servo_id = cmd.get('id')
                position = cmd.get('position')
                speed = cmd.get('speed', 500)
                if servo_id is not None and position is not None:
                    self._print(f"[DEBUG] 执行 move: ID={servo_id}, pos={position}, speed={speed}")
                    self.driver.move(servo_id, position, speed)
                    self._current_positions[servo_id] = position
            else:
                self._print(f"[DEBUG] move 被跳过: position_locked={self._position_locked}")
                
        elif cmd_type == 'sync_move':
            if not self._position_locked:
                positions = cmd.get('positions', {})
                speed = cmd.get('speed', 500)
                self.driver.sync_move(positions, speed)
                self._current_positions.update(positions)
            
        elif cmd_type == 'home':
            self._home()
            
        elif cmd_type == 'lock':
            self._position_locked = True
            self._print("位置已锁定")
            
        elif cmd_type == 'unlock':
            self._position_locked = False
            self._print("位置已解锁")
    
    def _home(self):
        """回到初始位置"""
        home_pos = {sid: 512 for sid in self.servo_ids}
        self.driver.sync_move(home_pos, speed=200)
        self._current_positions = home_pos.copy()
    
    def _do_init(self):
        """执行真正的初始化（扫描舵机、归位）"""
        self._print("开始初始化舵机...")
        
        # 扫描在线舵机
        online = []
        for sid in self.servo_ids:
            pos = self.driver.read_position(sid)
            if pos is not None:
                online.append(sid)
                self._current_positions[sid] = pos
        
        self._print(f"在线舵机: {online}")
        
        # 回到初始位置
        self._home()
        
        self._servo_initialized = True
        self._print("舵机初始化完成")
    
    # ==================== 外部接口 ====================
    
    def init(self):
        """初始化舵机（延迟初始化，进入模式时调用）"""
        # 立即恢复通信（不等队列处理）
        self._suspended = False
        self._print(f"[DEBUG] init() 调用: 立即设置 suspended=False")
        self._command_queue.put({'type': 'init'})
    
    def suspend(self):
        """暂停舵机通信（退出模式时调用，让出 USB 带宽给语音）"""
        self._command_queue.put({'type': 'suspend'})
    
    def resume(self):
        """恢复舵机通信"""
        self._command_queue.put({'type': 'resume'})
    
    def play_action(self, action_name: str):
        """播放动作"""
        self._command_queue.put({
            'type': 'play_action',
            'action': action_name
        })
    
    def stop_action(self):
        """停止动作"""
        self._command_queue.put({'type': 'stop_action'})
    
    def move(self, servo_id: int, position: int, speed: int = 500):
        """移动单个舵机"""
        self._print(f"[DEBUG] move() 被调用: ID={servo_id}, pos={position}")
        self._command_queue.put({
            'type': 'move',
            'id': servo_id,
            'position': position,
            'speed': speed
        })
    
    def sync_move(self, positions: Dict[int, int], speed: int = 500):
        """同步移动多个舵机"""
        self._command_queue.put({
            'type': 'sync_move',
            'positions': positions,
            'speed': speed
        })
    
    def home(self):
        """回到初始位置"""
        self._command_queue.put({'type': 'home'})
    
    def hold_position(self):
        """锁定当前位置"""
        self._command_queue.put({'type': 'lock'})
    
    def release_position(self):
        """解锁位置"""
        self._command_queue.put({'type': 'unlock'})
    
    def get_positions(self) -> Dict[int, int]:
        """获取当前位置"""
        return self._current_positions.copy()
    
    def stop(self):
        """停止线程"""
        self._running = False
        try:
            if self.is_alive():
                self.join(timeout=3)
        except (AssertionError, RuntimeError):
            # 线程可能尚未启动
            pass
    
    @property
    def is_playing(self) -> bool:
        """是否正在播放动作"""
        return self.action_player.is_playing
    
    @property
    def is_locked(self) -> bool:
        """位置是否锁定"""
        return self._position_locked
    
    def _print(self, message: str):
        """格式化打印"""
        print(f"[Servo] {message}")


# ==================== 独立测试 ====================
def test_servo_thread():
    """测试舵机线程"""
    print("=" * 50)
    print("舵机线程测试")
    print("=" * 50)
    
    config = {
        'port': '/dev/ttyUSB0',  # 根据实际情况修改
        'baudrate': 115200,
        'servo_ids': [1, 2, 3],
        'actions_file': 'config/actions.yaml',
    }
    
    # 检查是否能导入舵机 SDK
    try:
        from .servo_driver import ServoDriver
    except ImportError:
        print("警告: 舵机 SDK 未安装，使用模拟模式")
        print("请将 scservo_sdk 复制到 modules/servo/ 目录")
        return
    
    servo = ServoThread(config)
    servo.start()
    
    time.sleep(1)  # 等待初始化
    
    try:
        print("\n测试命令:")
        print("  1. 归中")
        print("  2. 点头")
        print("  3. 摇头")
        print("  4. 锁定位置")
        print("  5. 解锁位置")
        print("  q. 退出")
        
        while True:
            cmd = input("\n请输入命令: ").strip()
            
            if cmd == 'q':
                break
            elif cmd == '1':
                servo.home()
            elif cmd == '2':
                servo.play_action('nod')
            elif cmd == '3':
                servo.play_action('shake')
            elif cmd == '4':
                servo.hold_position()
            elif cmd == '5':
                servo.release_position()
            else:
                print("未知命令")
            
    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        servo.stop()
        print("测试结束")


if __name__ == "__main__":
    test_servo_thread()
