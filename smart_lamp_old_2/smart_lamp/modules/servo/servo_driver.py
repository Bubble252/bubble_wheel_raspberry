"""
飞特总线舵机驱动
参考: FTServo_Python/my_servo_control.py
"""
import time
import threading
from typing import Dict, List, Optional, Tuple


class ServoDriver:
    """
    飞特总线舵机驱动
    通过USB串口控制SMS_STS系列舵机
    """
    
    # 寄存器地址
    STS_GOAL_POSITION_L = 42
    STS_PRESENT_POSITION_L = 56
    STS_TORQUE_ENABLE = 40
    
    def __init__(self, port: str = "/dev/ttyUSB0", baudrate: int = 1000000):
        """
        初始化舵机驱动
        
        Args:
            port: 串口端口
            baudrate: 波特率
        """
        self.port = port
        self.baudrate = baudrate
        
        self._port_handler = None
        self._packet_handler = None
        self._lock = threading.Lock()
        self._connected = False
        
        # 尝试导入 scservo_sdk
        self._sdk_available = False
        try:
            from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS
            self._PortHandler = PortHandler
            self._sms_sts = sms_sts
            self._COMM_SUCCESS = COMM_SUCCESS
            self._sdk_available = True
        except ImportError:
            print("scservo_sdk 未安装，舵机控制不可用")
            print("请从 FTServo_Python/scservo_sdk 复制到项目目录")
    
    def connect(self) -> bool:
        """
        连接舵机
        
        Returns:
            是否成功连接
        """
        if not self._sdk_available:
            return False
        
        if self._connected:
            return True
        
        try:
            self._port_handler = self._PortHandler(self.port)
            self._packet_handler = self._sms_sts(self._port_handler)
            
            if not self._port_handler.openPort():
                print(f"无法打开串口: {self.port}")
                return False
            
            if not self._port_handler.setBaudRate(self.baudrate):
                print(f"无法设置波特率: {self.baudrate}")
                return False
            
            self._connected = True
            print(f"舵机连接成功: {self.port} @ {self.baudrate}")
            return True
            
        except Exception as e:
            print(f"舵机连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self._port_handler:
            try:
                self._port_handler.closePort()
            except:
                pass
        self._connected = False
    
    def move(self, servo_id: int, position: int, speed: int = 500) -> bool:
        """
        移动舵机到指定位置
        
        Args:
            servo_id: 舵机ID
            position: 目标位置 (0-1000)
            speed: 速度
            
        Returns:
            是否成功
        """
        if not self._connected:
            if not self.connect():
                return False
        
        with self._lock:
            try:
                # 位置限幅
                position = max(0, min(1000, position))
                
                # 构造数据包 (大端序)
                data = [
                    (position >> 8) & 0xFF,  # 位置高字节
                    position & 0xFF,          # 位置低字节
                    0, 0,                     # 时间（不使用）
                    (speed >> 8) & 0xFF,      # 速度高字节
                    speed & 0xFF              # 速度低字节
                ]
                
                result = self._packet_handler.writeTxRx(
                    servo_id, self.STS_GOAL_POSITION_L, len(data), data
                )
                
                return result == self._COMM_SUCCESS
                
            except Exception as e:
                print(f"舵机移动失败 [ID:{servo_id}]: {e}")
                return False
    
    def move_all(self, positions: Dict[int, int], speed: int = 500) -> bool:
        """
        同时移动多个舵机
        
        Args:
            positions: {舵机ID: 位置} 字典
            speed: 速度
            
        Returns:
            是否全部成功
        """
        success = True
        for servo_id, position in positions.items():
            if not self.move(servo_id, position, speed):
                success = False
            time.sleep(0.01)  # 小延迟，避免总线冲突
        return success
    
    def read_position(self, servo_id: int) -> Optional[int]:
        """
        读取舵机当前位置
        
        Args:
            servo_id: 舵机ID
            
        Returns:
            当前位置，失败返回 None
        """
        if not self._connected:
            if not self.connect():
                return None
        
        with self._lock:
            try:
                pos_raw, result, error = self._packet_handler.read2ByteTxRx(
                    servo_id, self.STS_PRESENT_POSITION_L
                )
                
                if result == self._COMM_SUCCESS:
                    # 交换字节顺序
                    pos = ((pos_raw & 0xFF) << 8) | ((pos_raw >> 8) & 0xFF)
                    return pos
                return None
                
            except Exception as e:
                print(f"读取位置失败 [ID:{servo_id}]: {e}")
                return None
    
    def read_all_positions(self, servo_ids: List[int]) -> Dict[int, int]:
        """
        读取多个舵机位置
        
        Args:
            servo_ids: 舵机ID列表
            
        Returns:
            {舵机ID: 位置} 字典
        """
        positions = {}
        for servo_id in servo_ids:
            pos = self.read_position(servo_id)
            if pos is not None:
                positions[servo_id] = pos
            time.sleep(0.01)
        return positions
    
    def set_torque(self, servo_id: int, enable: bool) -> bool:
        """
        设置舵机扭矩开关
        
        Args:
            servo_id: 舵机ID
            enable: 是否使能
            
        Returns:
            是否成功
        """
        if not self._connected:
            return False
        
        with self._lock:
            try:
                value = 1 if enable else 0
                result = self._packet_handler.write1ByteTxRx(
                    servo_id, self.STS_TORQUE_ENABLE, value
                )
                return result == self._COMM_SUCCESS
            except:
                return False
    
    def ping(self, servo_id: int) -> bool:
        """
        检测舵机是否在线
        
        Args:
            servo_id: 舵机ID
            
        Returns:
            是否在线
        """
        pos = self.read_position(servo_id)
        return pos is not None
    
    def scan(self, id_range: range = range(1, 10)) -> List[int]:
        """
        扫描在线舵机
        
        Args:
            id_range: ID扫描范围
            
        Returns:
            在线舵机ID列表
        """
        online = []
        for servo_id in id_range:
            if self.ping(servo_id):
                online.append(servo_id)
        return online
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected
    
    def __del__(self):
        self.disconnect()
