"""
摄像头管理器
封装摄像头的打开、读取、释放等操作
"""
import cv2
import threading
import time
from typing import Optional, Tuple
import numpy as np


class Camera:
    """
    摄像头管理类
    提供线程安全的摄像头访问
    """
    
    def __init__(self, device_id: int = 0, width: int = 640, height: int = 480, fps: int = 15):
        """
        初始化摄像头
        
        Args:
            device_id: 摄像头设备ID
            width: 图像宽度
            height: 图像高度
            fps: 帧率
        """
        self.device_id = device_id
        self.width = width
        self.height = height
        self.fps = fps
        
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._frame_time: float = 0
        self._lock = threading.Lock()
        self._running = False
        self._read_thread: Optional[threading.Thread] = None
    
    def open(self) -> bool:
        """
        打开摄像头
        
        Returns:
            是否成功打开
        """
        if self._cap is not None:
            return True
        
        self._cap = cv2.VideoCapture(self.device_id)
        
        if not self._cap.isOpened():
            self._cap = None
            return False
        
        # 设置参数
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        self._cap.set(cv2.CAP_PROP_FPS, self.fps)
        
        # 减少缓冲区大小，降低延迟
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        
        return True
    
    def close(self):
        """关闭摄像头"""
        self.stop_continuous_read()
        
        if self._cap is not None:
            self._cap.release()
            self._cap = None
    
    def read(self) -> Optional[np.ndarray]:
        """
        读取一帧图像
        
        Returns:
            BGR图像，失败返回None
        """
        if self._cap is None:
            if not self.open():
                return None
        
        ret, frame = self._cap.read()
        if ret:
            return frame
        return None
    
    def read_rgb(self) -> Optional[np.ndarray]:
        """
        读取RGB格式图像
        
        Returns:
            RGB图像
        """
        frame = self.read()
        if frame is not None:
            return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return None
    
    def start_continuous_read(self):
        """
        启动连续读取线程
        在后台持续读取，减少主线程获取图像的延迟
        """
        if self._running:
            return
        
        if not self.open():
            return
        
        self._running = True
        self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
        self._read_thread.start()
    
    def stop_continuous_read(self):
        """停止连续读取"""
        self._running = False
        if self._read_thread:
            self._read_thread.join(timeout=1)
            self._read_thread = None
    
    def _read_loop(self):
        """连续读取循环"""
        while self._running:
            ret, frame = self._cap.read()
            if ret:
                with self._lock:
                    self._frame = frame
                    self._frame_time = time.time()
            time.sleep(0.001)  # 小延迟，避免CPU占用过高
    
    def get_latest_frame(self) -> Tuple[Optional[np.ndarray], float]:
        """
        获取最新帧（用于连续读取模式）
        
        Returns:
            (图像, 时间戳) 元组
        """
        with self._lock:
            return self._frame.copy() if self._frame is not None else None, self._frame_time
    
    def get_latest_rgb(self) -> Tuple[Optional[np.ndarray], float]:
        """获取最新的RGB帧"""
        frame, timestamp = self.get_latest_frame()
        if frame is not None:
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return frame, timestamp
    
    @property
    def is_opened(self) -> bool:
        """摄像头是否已打开"""
        return self._cap is not None and self._cap.isOpened()
    
    @property
    def actual_size(self) -> Tuple[int, int]:
        """获取实际的图像尺寸"""
        if self._cap is None:
            return 0, 0
        w = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return w, h
    
    def __enter__(self):
        self.open()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
