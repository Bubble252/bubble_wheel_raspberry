"""
手势检测器
使用 MediaPipe Hands
参考: handpose/single_hand_detector_improved.py
"""
import numpy as np
from typing import Optional, Tuple, Dict
from enum import Enum


class GestureType(Enum):
    """手势类型"""
    NONE = "none"
    OPEN_PALM = "open_palm"      # 张开手掌
    FIST = "fist"               # 握拳
    THUMBS_UP = "thumbs_up"     # 点赞
    THUMBS_DOWN = "thumbs_down" # 倒赞
    POINTING = "pointing"       # 指向
    WAVE = "wave"               # 挥手


class GestureDetector:
    """
    手势检测器
    基于 MediaPipe Hands
    """
    
    def __init__(self, min_detection_confidence: float = 0.7, 
                 min_tracking_confidence: float = 0.5):
        """
        初始化手势检测器
        
        Args:
            min_detection_confidence: 检测置信度阈值
            min_tracking_confidence: 跟踪置信度阈值
        """
        self.mp_hands = None
        self.hands = None
        self.initialized = False
        
        try:
            import mediapipe as mp
            self.mp_hands = mp.solutions.hands
            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence
            )
            self.initialized = True
            print("手势检测: 使用 MediaPipe")
        except ImportError:
            print("MediaPipe 未安装，手势检测不可用")
            print("安装命令: pip install mediapipe")
    
    def detect(self, rgb_frame: np.ndarray) -> Optional[Dict]:
        """
        检测手势
        
        Args:
            rgb_frame: RGB 格式图像
            
        Returns:
            {'gesture': str, 'confidence': float, 'landmarks': array}
        """
        if not self.initialized or rgb_frame is None:
            return None
        
        results = self.hands.process(rgb_frame)
        
        if not results.multi_hand_landmarks:
            return None
        
        # 获取第一只手的关键点
        hand_landmarks = results.multi_hand_landmarks[0]
        
        # 转换为数组
        landmarks = self._landmarks_to_array(hand_landmarks, rgb_frame.shape)
        
        # 识别手势
        gesture = self._recognize_gesture(landmarks)
        
        return {
            'gesture': gesture.value,
            'confidence': 0.8,  # MediaPipe 不直接提供手势置信度
            'landmarks': landmarks
        }
    
    def _landmarks_to_array(self, hand_landmarks, image_shape) -> np.ndarray:
        """将 MediaPipe 关键点转换为数组"""
        h, w = image_shape[:2]
        landmarks = np.zeros((21, 3))
        
        for i, lm in enumerate(hand_landmarks.landmark):
            landmarks[i] = [lm.x * w, lm.y * h, lm.z]
        
        return landmarks
    
    def _recognize_gesture(self, landmarks: np.ndarray) -> GestureType:
        """
        识别手势
        
        基于手指伸展状态判断手势
        """
        # 计算手指是否伸展
        fingers_extended = self._get_fingers_extended(landmarks)
        
        # 根据手指状态判断手势
        thumb, index, middle, ring, pinky = fingers_extended
        
        # 张开手掌：所有手指伸展
        if all(fingers_extended):
            return GestureType.OPEN_PALM
        
        # 握拳：所有手指弯曲
        if not any(fingers_extended):
            return GestureType.FIST
        
        # 点赞：只有拇指伸展
        if thumb and not any([index, middle, ring, pinky]):
            # 检查拇指朝向
            if landmarks[4][1] < landmarks[3][1]:  # 拇指向上
                return GestureType.THUMBS_UP
            else:
                return GestureType.THUMBS_DOWN
        
        # 指向：只有食指伸展
        if index and not any([middle, ring, pinky]):
            return GestureType.POINTING
        
        return GestureType.NONE
    
    def _get_fingers_extended(self, landmarks: np.ndarray) -> Tuple[bool, bool, bool, bool, bool]:
        """
        判断各手指是否伸展
        
        Returns:
            (拇指, 食指, 中指, 无名指, 小指) 是否伸展
        """
        # 手指指尖和关节的索引
        # 拇指: 4 (tip), 3, 2
        # 食指: 8 (tip), 7, 6, 5
        # 中指: 12 (tip), 11, 10, 9
        # 无名指: 16 (tip), 15, 14, 13
        # 小指: 20 (tip), 19, 18, 17
        
        # 拇指判断（基于x坐标，因为拇指横向）
        thumb = landmarks[4][0] > landmarks[3][0]  # 简化判断
        
        # 其他手指判断（基于y坐标，指尖比关节更上方则伸展）
        index = landmarks[8][1] < landmarks[6][1]
        middle = landmarks[12][1] < landmarks[10][1]
        ring = landmarks[16][1] < landmarks[14][1]
        pinky = landmarks[20][1] < landmarks[18][1]
        
        return thumb, index, middle, ring, pinky
    
    def get_hand_openness(self, landmarks: np.ndarray) -> float:
        """
        计算手掌张开程度
        
        Returns:
            0.0 (握拳) ~ 1.0 (完全张开)
        """
        if landmarks is None:
            return 0.5
        
        # 计算手掌中心
        palm_center = np.mean(landmarks[[0, 5, 9, 13, 17]], axis=0)
        
        # 计算指尖到手掌中心的平均距离
        fingertips = landmarks[[4, 8, 12, 16, 20]]
        distances = np.linalg.norm(fingertips[:, :2] - palm_center[:2], axis=1)
        
        # 归一化
        palm_width = np.linalg.norm(landmarks[5][:2] - landmarks[17][:2])
        if palm_width < 1:
            palm_width = 1
        
        openness = np.mean(distances) / palm_width
        return float(np.clip(openness, 0.0, 1.5) / 1.5)
    
    def close(self):
        """释放资源"""
        if self.hands:
            self.hands.close()
