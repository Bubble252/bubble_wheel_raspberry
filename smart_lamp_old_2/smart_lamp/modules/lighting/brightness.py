"""
亮度控制器
通过 UART 串口向 STM32 发送亮度值 (0.0 ~ 1.0)
"""
import serial
import threading
import time
from typing import Optional


class BrightnessController:
    """
    亮度控制器
    通过串口向 STM32 发送目标亮度值
    """
    
    def __init__(self, config: dict):
        """
        初始化亮度控制器
        
        Args:
            config: 配置字典
        """
        stm32_config = config.get('stm32', {})
        
        self.port = stm32_config.get('port', '/dev/ttyAMA0')
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
        
        # 确保连接
        if not self._connected:
            if not self.connect():
                print(f"[模拟] 设置亮度: {brightness:.3f}")
                return True  # 模拟模式
        
        with self._lock:
            try:
                # 发送亮度值（简单文本协议）
                # 格式: "0.750\n"
                data = f"{brightness:.3f}\n"
                self._serial.write(data.encode('utf-8'))
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
            实际亮度值，失败返回 None
        """
        if not self._connected:
            return None
        
        with self._lock:
            try:
                # 发送查询命令
                self._serial.write(b"?\n")
                self._serial.flush()
                
                # 等待响应
                time.sleep(0.1)
                
                if self._serial.in_waiting > 0:
                    response = self._serial.readline().decode('utf-8').strip()
                    return float(response)
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
