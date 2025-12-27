"""
亮度控制器
通过 USB 虚拟串口向 STM32 发送亮度值

协议格式：2字节
  - 字节1: 帧头 0xAA
  - 字节2: 亮度值 67~101（67=关灯/0%，101=最亮/100%）
  
注意：避免发送 0x00
"""
import serial
import threading
import time
from typing import Optional


class BrightnessController:
    """
    亮度控制器
    通过串口向 STM32 发送目标亮度值
    
    协议：[0xAA] [亮度值]
      - 帧头: 0xAA
      - 亮度值: 67~101 (67=0%, 101=100%)
      - 避免发送 0x00
    """
    
    # 帧头
    FRAME_HEADER = 0xAA
    
    # 亮度值范围
    BRIGHTNESS_MIN = 67   # 对应 0%
    BRIGHTNESS_MAX = 101  # 对应 100%
    
    def __init__(self, config: dict):
        """
        初始化亮度控制器
        
        Args:
            config: 配置字典
        """
        stm32_config = config.get('stm32', {})
        
        self.port = stm32_config.get('port', '/dev/ttyACM0')
        self.baudrate = stm32_config.get('baudrate', 115200)
        self.timeout = stm32_config.get('timeout', 1)
        
        self._serial: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self._current_brightness = 0.5
        self._connected = False
    
    def connect(self) -> bool:
        """
        连接串口
        
        Returns:
            是否成功
        """
        if self._connected:
            return True
        
        try:
            self._serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout
            )
            self._connected = True
            print(f"STM32 连接成功: {self.port}")
            return True
        except Exception as e:
            print(f"STM32 连接失败: {e}")
            return False
    
    def close(self):
        """关闭连接"""
        if self._serial:
            try:
                self._serial.close()
            except:
                pass
            self._serial = None
        self._connected = False
    
    @property
    def current_brightness(self) -> float:
        """获取当前亮度值"""
        return self._current_brightness
    
    def set(self, brightness: float) -> bool:
        """
        设置亮度
        
        Args:
            brightness: 亮度值 0.0 ~ 1.0
            
        Returns:
            是否成功
        """
        # 限幅
        brightness = max(0.0, min(1.0, brightness))
        self._current_brightness = brightness
        
        # 将 0.0~1.0 映射到 67~101 的整数
        # 0.0 -> 67, 1.0 -> 101
        level = round(brightness * (self.BRIGHTNESS_MAX - self.BRIGHTNESS_MIN) + self.BRIGHTNESS_MIN)
        level = max(self.BRIGHTNESS_MIN, min(self.BRIGHTNESS_MAX, level))
        
        # 确保连接
        if not self._connected:
            if not self.connect():
                print(f"[模拟] 设置亮度: {brightness:.2f} -> level {level}")
                return True  # 模拟模式
        
        with self._lock:
            try:
                # 发送两字节: [帧头 0xAA] [亮度值 67~101]
                data = bytes([self.FRAME_HEADER, level])
                self._serial.write(data)
                self._serial.flush()
                return True
            except Exception as e:
                print(f"发送亮度失败: {e}")
                self._connected = False
                return False
    
    def set_percent(self, percent: int) -> bool:
        """
        设置亮度百分比
        
        Args:
            percent: 0 ~ 100
        """
        return self.set(percent / 100.0)
    
    def increase(self, delta: float = 0.1) -> float:
        """
        增加亮度
        
        Args:
            delta: 增量
            
        Returns:
            新的亮度值
        """
        new_brightness = min(1.0, self._current_brightness + delta)
        self.set(new_brightness)
        return new_brightness
    
    def decrease(self, delta: float = 0.1) -> float:
        """
        降低亮度
        
        Args:
            delta: 减量
            
        Returns:
            新的亮度值
        """
        new_brightness = max(0.0, self._current_brightness - delta)
        self.set(new_brightness)
        return new_brightness
    
    def on(self, brightness: float = 0.8) -> bool:
        """开灯"""
        return self.set(brightness)
    
    def off(self) -> bool:
        """关灯"""
        return self.set(0.0)
    
    def read_actual(self) -> Optional[float]:
        """
        读取实际亮度（从 STM32 反馈）
        
        Returns:
            实际亮度值 (0.0~1.0)，失败返回 None
        """
        if not self._connected:
            return None
        
        with self._lock:
            try:
                # 发送查询命令 (0xFF 作为查询指令)
                self._serial.write(bytes([0xFF]))
                self._serial.flush()
                
                # 等待响应
                time.sleep(0.1)
                
                if self._serial.in_waiting > 0:
                    # 读取单字节响应 (0~10)
                    response = self._serial.read(1)
                    if response:
                        level = response[0]
                        return level / 10.0  # 转回 0.0~1.0
            except:
                pass
        
        return None
    
    @property
    def brightness(self) -> float:
        """当前设定亮度"""
        return self._current_brightness
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected
    
    @property
    def is_on(self) -> bool:
        """灯是否开启"""
        return self._current_brightness > 0.01
    
    def __del__(self):
        self.close()
