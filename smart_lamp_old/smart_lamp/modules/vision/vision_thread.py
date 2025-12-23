"""
视觉处理线程
整合人脸检测、情绪识别、手势识别
"""
import threading
import time
from typing import Optional
from queue import Queue

from .camera import Camera
from .face_detector import FaceDetector
from .emotion_detector import EmotionDetector
from .gesture_detector import GestureDetector
from ...core.message_bus import MessageBus, Message, MessageType


class VisionThread(threading.Thread):
    """
    视觉处理线程
    在后台持续处理摄像头图像，发布检测结果
    """
    
    def __init__(self, message_bus: MessageBus, config: dict):
        """
        初始化视觉线程
        
        Args:
            message_bus: 消息总线
            config: 配置字典
        """
        super().__init__(daemon=True, name="VisionThread")
        
        self.message_bus = message_bus
        self.config = config
        self._running = False
        
        # 从配置获取参数
        cam_config = config.get('devices', {}).get('camera', {})
        vision_config = config.get('modules', {}).get('vision', {})
        
        # 初始化摄像头
        self.camera = Camera(
            device_id=cam_config.get('device_id', 0),
            width=cam_config.get('width', 640),
            height=cam_config.get('height', 480),
            fps=cam_config.get('fps', 15)
        )
        
        # 初始化检测器
        self.face_detector = None
        self.emotion_detector = None
        self.gesture_detector = None
        
        if vision_config.get('face_detection', True):
            self.face_detector = FaceDetector(model_path="models/")
        
        if vision_config.get('emotion_detection', True):
            self.emotion_detector = EmotionDetector(use_fer=True)
        
        if vision_config.get('gesture_detection', True):
            self.gesture_detector = GestureDetector()
        
        # 处理间隔
        self.process_interval = vision_config.get('process_interval', 0.1)
        
        # 状态跟踪
        self._face_detected = False
        self._last_emotion = None
        self._last_gesture = None
    
    def run(self):
        """线程主循环"""
        print("视觉线程启动")
        self._running = True
        
        # 打开摄像头
        if not self.camera.open():
            print("摄像头打开失败")
            self.message_bus.publish_event(
                MessageType.MODULE_ERROR,
                data={'module': 'vision', 'error': '摄像头打开失败'},
                source='vision'
            )
            return
        
        self.message_bus.publish_event(
            MessageType.MODULE_STARTED,
            data={'module': 'vision'},
            source='vision'
        )
        
        last_process_time = 0
        
        while self._running:
            current_time = time.time()
            
            # 控制处理频率
            if current_time - last_process_time < self.process_interval:
                time.sleep(0.01)
                continue
            
            last_process_time = current_time
            
            # 读取图像
            frame = self.camera.read()
            if frame is None:
                time.sleep(0.1)
                continue
            
            # 处理图像
            self._process_frame(frame)
        
        # 清理
        self.camera.close()
        if self.gesture_detector:
            self.gesture_detector.close()
        
        print("视觉线程退出")
    
    def _process_frame(self, frame):
        """处理单帧图像"""
        import cv2
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 人脸检测
        if self.face_detector:
            faces = self.face_detector.detect(frame)
            
            if faces:
                face = faces[0]  # 只处理第一个人脸
                
                # 人脸首次出现
                if not self._face_detected:
                    self._face_detected = True
                    self.message_bus.publish_event(
                        MessageType.FACE_DETECTED,
                        data={'face': face, 'is_new': True},
                        source='vision'
                    )
                
                # 情绪检测
                if self.emotion_detector:
                    emotion_result = self.emotion_detector.detect(frame, face)
                    
                    if emotion_result:
                        emotion = emotion_result['emotion']
                        
                        # 只在情绪变化时发送
                        if emotion != self._last_emotion:
                            self._last_emotion = emotion
                            self.message_bus.publish_event(
                                MessageType.EMOTION_CHANGED,
                                data={
                                    'emotion': emotion,
                                    'confidence': emotion_result['confidence'],
                                    'all_emotions': emotion_result.get('all_emotions', {})
                                },
                                source='vision'
                            )
            else:
                # 人脸丢失
                if self._face_detected:
                    self._face_detected = False
                    self._last_emotion = None
                    self.message_bus.publish_event(
                        MessageType.FACE_LOST,
                        source='vision'
                    )
        
        # 手势检测
        if self.gesture_detector:
            gesture_result = self.gesture_detector.detect(rgb_frame)
            
            if gesture_result and gesture_result['gesture'] != 'none':
                gesture = gesture_result['gesture']
                
                # 只在手势变化时发送
                if gesture != self._last_gesture:
                    self._last_gesture = gesture
                    self.message_bus.publish_event(
                        MessageType.GESTURE_DETECTED,
                        data={
                            'gesture': gesture,
                            'confidence': gesture_result['confidence']
                        },
                        source='vision'
                    )
            else:
                self._last_gesture = None
    
    def stop(self):
        """停止线程"""
        self._running = False
        self.join(timeout=2)
    
    @property
    def is_face_detected(self) -> bool:
        """当前是否检测到人脸"""
        return self._face_detected
