"""
消息总线 - 模块间通信
使用 queue.Queue 实现线程安全的消息传递
"""
import time
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Optional, Callable, Dict, List
from queue import Queue, Empty
import threading


class MessageType(Enum):
    """消息类型枚举"""
    # 视觉事件
    FACE_DETECTED = auto()
    FACE_LOST = auto()
    EMOTION_CHANGED = auto()
    GESTURE_DETECTED = auto()
    
    # 语音事件
    WAKE_WORD = auto()
    VOICE_COMMAND = auto()
    
    # 控制命令
    SET_BRIGHTNESS = auto()
    PLAY_ACTION = auto()
    STOP_ACTION = auto()
    SERVO_MOVE = auto()
    
    # 系统事件
    MODULE_STARTED = auto()
    MODULE_STOPPED = auto()
    MODULE_ERROR = auto()
    STATE_CHANGED = auto()
    
    # 生命周期
    SHUTDOWN = auto()
    HEARTBEAT = auto()


@dataclass
class Message:
    """消息数据类"""
    type: MessageType
    data: Any = None
    source: str = ""  # 消息来源模块
    timestamp: float = field(default_factory=time.time)
    
    def __repr__(self):
        return f"Message({self.type.name}, data={self.data}, from={self.source})"


class MessageBus:
    """
    消息总线
    负责模块间的消息传递和事件分发
    """
    
    def __init__(self, max_size: int = 1000):
        """
        初始化消息总线
        
        Args:
            max_size: 队列最大容量
        """
        self._queue = Queue(maxsize=max_size)
        self._subscribers: Dict[MessageType, List[Callable]] = {}
        self._running = False
        self._dispatch_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def publish(self, message: Message) -> bool:
        """
        发布消息到总线
        
        Args:
            message: 消息对象
            
        Returns:
            是否成功放入队列
        """
        try:
            self._queue.put_nowait(message)
            return True
        except:
            return False
    
    def publish_event(self, msg_type: MessageType, data: Any = None, source: str = "") -> bool:
        """
        发布事件的便捷方法
        
        Args:
            msg_type: 消息类型
            data: 消息数据
            source: 来源模块
        """
        return self.publish(Message(type=msg_type, data=data, source=source))
    
    def get(self, timeout: float = None) -> Optional[Message]:
        """
        获取消息（阻塞）
        
        Args:
            timeout: 超时时间(秒)，None表示永久等待
            
        Returns:
            消息对象，超时返回None
        """
        try:
            return self._queue.get(timeout=timeout)
        except Empty:
            return None
    
    def get_nowait(self) -> Optional[Message]:
        """
        获取消息（非阻塞）
        
        Returns:
            消息对象，队列空返回None
        """
        try:
            return self._queue.get_nowait()
        except Empty:
            return None
    
    def subscribe(self, msg_type: MessageType, callback: Callable[[Message], None]):
        """
        订阅特定类型的消息
        
        Args:
            msg_type: 消息类型
            callback: 回调函数，接收Message参数
        """
        with self._lock:
            if msg_type not in self._subscribers:
                self._subscribers[msg_type] = []
            self._subscribers[msg_type].append(callback)
    
    def unsubscribe(self, msg_type: MessageType, callback: Callable):
        """取消订阅"""
        with self._lock:
            if msg_type in self._subscribers:
                try:
                    self._subscribers[msg_type].remove(callback)
                except ValueError:
                    pass
    
    def start_dispatch(self):
        """启动消息分发线程"""
        if self._running:
            return
            
        self._running = True
        self._dispatch_thread = threading.Thread(target=self._dispatch_loop, daemon=True)
        self._dispatch_thread.start()
    
    def stop_dispatch(self):
        """停止消息分发"""
        self._running = False
        # 发送一个空消息来唤醒阻塞的get
        self.publish_event(MessageType.SHUTDOWN)
        if self._dispatch_thread:
            self._dispatch_thread.join(timeout=2)
    
    def _dispatch_loop(self):
        """消息分发循环"""
        while self._running:
            msg = self.get(timeout=0.1)
            if msg is None:
                continue
                
            # 分发给订阅者
            with self._lock:
                callbacks = self._subscribers.get(msg.type, []).copy()
            
            for callback in callbacks:
                try:
                    callback(msg)
                except Exception as e:
                    print(f"消息处理错误: {e}")
    
    def clear(self):
        """清空队列"""
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Empty:
                break
    
    @property
    def size(self) -> int:
        """当前队列大小"""
        return self._queue.qsize()
    
    @property
    def is_empty(self) -> bool:
        """队列是否为空"""
        return self._queue.empty()
