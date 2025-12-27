"""
音频采集器
封装 PyAudio 的音频采集功能
"""
import threading
from typing import Optional, Callable
import time


class AudioCapture:
    """
    音频采集器
    从麦克风采集音频数据
    """
    
    def __init__(self, device_index: int = None, sample_rate: int = 16000, 
                 chunk_size: int = 1024, channels: int = 1):
        """
        初始化音频采集器
        
        Args:
            device_index: 麦克风设备索引，None 表示默认
            sample_rate: 采样率
            chunk_size: 每次读取的采样数
            channels: 声道数
        """
        self.device_index = device_index
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        
        self._pyaudio = None
        self._stream = None
        self._running = False
        self._callback: Optional[Callable] = None
        self._thread: Optional[threading.Thread] = None
        
        # 尝试导入 PyAudio
        try:
            import pyaudio
            self._pyaudio = pyaudio.PyAudio()
            print("音频采集: PyAudio 初始化成功")
        except ImportError:
            print("PyAudio 未安装")
            print("安装命令: pip install pyaudio")
        except Exception as e:
            print(f"PyAudio 初始化失败: {e}")
    
    def list_devices(self):
        """列出所有音频设备"""
        if self._pyaudio is None:
            print("PyAudio 未初始化")
            return []
        
        devices = []
        for i in range(self._pyaudio.get_device_count()):
            info = self._pyaudio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                devices.append({
                    'index': i,
                    'name': info['name'],
                    'channels': info['maxInputChannels'],
                    'sample_rate': int(info['defaultSampleRate'])
                })
                print(f"  [{i}] {info['name']} (输入通道: {info['maxInputChannels']})")
        
        return devices
    
    def open(self) -> bool:
        """
        打开音频流
        
        Returns:
            是否成功
        """
        if self._pyaudio is None:
            return False
        
        if self._stream is not None:
            return True
        
        try:
            import pyaudio
            self._stream = self._pyaudio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size
            )
            return True
        except Exception as e:
            print(f"打开音频流失败: {e}")
            return False
    
    def close(self):
        """关闭音频流"""
        self.stop_continuous()
        
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except:
                pass
            self._stream = None
    
    def read(self) -> Optional[bytes]:
        """
        读取一帧音频数据
        
        Returns:
            音频数据 (bytes)
        """
        if self._stream is None:
            if not self.open():
                return None
        
        try:
            return self._stream.read(self.chunk_size, exception_on_overflow=False)
        except Exception as e:
            print(f"读取音频失败: {e}")
            return None
    
    def read_seconds(self, seconds: float) -> Optional[bytes]:
        """
        读取指定时长的音频
        
        Args:
            seconds: 时长(秒)
            
        Returns:
            音频数据
        """
        if self._stream is None:
            if not self.open():
                return None
        
        frames = []
        num_chunks = int(self.sample_rate / self.chunk_size * seconds)
        
        for _ in range(num_chunks):
            data = self.read()
            if data:
                frames.append(data)
        
        return b''.join(frames) if frames else None
    
    def start_continuous(self, callback: Callable[[bytes], None]):
        """
        开始连续采集
        
        Args:
            callback: 数据回调函数
        """
        if self._running:
            return
        
        if not self.open():
            return
        
        self._callback = callback
        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
    
    def stop_continuous(self):
        """停止连续采集"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1)
            self._thread = None
    
    def _capture_loop(self):
        """采集循环"""
        while self._running:
            data = self.read()
            if data and self._callback:
                try:
                    self._callback(data)
                except Exception as e:
                    print(f"音频回调错误: {e}")
    
    def __del__(self):
        """析构函数"""
        self.close()
        if self._pyaudio:
            try:
                self._pyaudio.terminate()
            except:
                pass
