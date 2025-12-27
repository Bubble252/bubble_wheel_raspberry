"""
动作播放器
根据动作库配置播放舵机动作序列
支持两种关键帧格式:
1. 旧格式: positions: {舵机ID: 编码}
2. 新格式: pose: {b: 值, theta_0: 值, beta: 值}
"""
import time
import threading
import yaml
from typing import Dict, List, Optional
from pathlib import Path

from .servo_driver import ServoDriver
from ...utils.kinematics import pose_to_encoders, interpolate_pose, get_home_encoders


class ActionPlayer:
    """
    动作播放器
    播放预定义的舵机动作序列
    """
    
    def __init__(self, servo_driver: ServoDriver, actions_config_path: str = "config/actions.yaml"):
        """
        初始化动作播放器
        
        Args:
            servo_driver: 舵机驱动实例
            actions_config_path: 动作配置文件路径
        """
        self.servo = servo_driver
        self.actions: Dict = {}
        
        self._playing = False
        self._current_action = None
        self._loop = False
        self._stop_flag = False
        self._play_thread: Optional[threading.Thread] = None
        
        # 加载动作库
        self._load_actions(actions_config_path)
    
    def _load_actions(self, config_path: str):
        """加载动作配置"""
        try:
            path = Path(config_path)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    config = yaml.safe_load(f)
                    self.actions = config.get('actions', {})
                print(f"加载了 {len(self.actions)} 个动作")
            else:
                print(f"动作配置文件不存在: {config_path}")
                self._load_default_actions()
        except Exception as e:
            print(f"加载动作配置失败: {e}")
            self._load_default_actions()
    
    def _keyframe_to_positions(self, kf: Dict) -> Dict[int, int]:
        """
        将关键帧转换为舵机位置
        
        支持两种格式:
        1. 旧格式: positions: {舵机ID: 编码}
        2. 新格式: pose: {b: 值, theta_0: 值, beta: 值}
        
        Args:
            kf: 关键帧字典
            
        Returns:
            舵机位置字典 {舵机ID: 编码}
        """
        # 优先使用新格式 (pose)
        if 'pose' in kf:
            pose = kf['pose']
            b = pose.get('b', 0.1)
            theta_0 = pose.get('theta_0', 90)
            beta = pose.get('beta', 0)
            
            positions, valid = pose_to_encoders(b, theta_0, beta)
            
            if not valid:
                print(f"警告: 无效的姿态 b={b}, theta_0={theta_0}, beta={beta}，使用默认位置")
                return get_home_encoders()
            
            return positions
        
        # 旧格式 (positions)
        elif 'positions' in kf:
            positions = kf.get('positions', {})
            # 转换键为整数
            return {int(k): v for k, v in positions.items()}
        
        # 无效格式
        return {}
    
    def _load_default_actions(self):
        """加载默认动作（使用新格式 pose）"""
        self.actions = {
            'nod': {
                'name': '点头',
                'loop': False,
                'duration': 800,
                'keyframes': [
                    {'time': 0, 'pose': {'b': 0.10, 'theta_0': 90, 'beta': 0}},
                    {'time': 400, 'pose': {'b': 0.12, 'theta_0': 90, 'beta': -20}},
                    {'time': 800, 'pose': {'b': 0.10, 'theta_0': 90, 'beta': 0}},
                ]
            },
            'shake': {
                'name': '摇头',
                'loop': False,
                'duration': 1000,
                'keyframes': [
                    {'time': 0, 'pose': {'b': 0.10, 'theta_0': 90, 'beta': 0}},
                    {'time': 250, 'pose': {'b': 0.10, 'theta_0': 70, 'beta': 0}},
                    {'time': 750, 'pose': {'b': 0.10, 'theta_0': 110, 'beta': 0}},
                    {'time': 1000, 'pose': {'b': 0.10, 'theta_0': 90, 'beta': 0}},
                ]
            },
            'home': {
                'name': '归位',
                'loop': False,
                'duration': 500,
                'keyframes': [
                    {'time': 0, 'pose': {'b': 0.10, 'theta_0': 90, 'beta': 0}},
                ]
            }
        }
    
    def play(self, action_name: str, blocking: bool = False) -> bool:
        """
        播放动作
        
        Args:
            action_name: 动作名称
            blocking: 是否阻塞等待完成
            
        Returns:
            是否成功开始播放
        """
        if action_name not in self.actions:
            print(f"动作不存在: {action_name}")
            return False
        
        # 停止当前动作
        self.stop()
        
        action = self.actions[action_name]
        self._current_action = action_name
        self._loop = action.get('loop', False)
        self._stop_flag = False
        self._playing = True
        
        if blocking:
            self._play_action(action)
        else:
            self._play_thread = threading.Thread(
                target=self._play_action, 
                args=(action,),
                daemon=True
            )
            self._play_thread.start()
        
        return True
    
    def _play_action(self, action: Dict):
        """播放动作的内部实现"""
        keyframes = action.get('keyframes', [])
        
        if not keyframes:
            self._playing = False
            return
        
        try:
            while not self._stop_flag:
                start_time = time.time() * 1000  # 毫秒
                
                for i, kf in enumerate(keyframes):
                    if self._stop_flag:
                        break
                    
                    # 获取舵机位置
                    positions = self._keyframe_to_positions(kf)
                    if positions:
                        self.servo.move_all(positions)
                    
                    # 计算等待时间
                    if i < len(keyframes) - 1:
                        next_time = keyframes[i + 1].get('time', 0)
                        current_time = kf.get('time', 0)
                        wait_time = (next_time - current_time) / 1000.0
                        
                        if wait_time > 0:
                            # 分段等待，便于响应停止信号
                            elapsed = 0
                            while elapsed < wait_time and not self._stop_flag:
                                sleep_time = min(0.05, wait_time - elapsed)
                                time.sleep(sleep_time)
                                elapsed += sleep_time
                
                # 循环或结束
                if not self._loop:
                    break
                    
        except Exception as e:
            print(f"播放动作错误: {e}")
        finally:
            self._playing = False
            self._current_action = None
    
    def stop(self):
        """停止当前动作"""
        self._stop_flag = True
        self._loop = False
        
        if self._play_thread and self._play_thread.is_alive():
            self._play_thread.join(timeout=1)
        
        self._playing = False
        self._current_action = None
    
    def home(self):
        """回到初始位置"""
        self.play('home', blocking=True)
    
    def get_action_list(self) -> List[str]:
        """获取所有动作名称"""
        return list(self.actions.keys())
    
    def get_action_info(self, action_name: str) -> Optional[Dict]:
        """获取动作信息"""
        return self.actions.get(action_name)
    
    @property
    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._playing
    
    @property
    def current_action(self) -> Optional[str]:
        """当前播放的动作"""
        return self._current_action
