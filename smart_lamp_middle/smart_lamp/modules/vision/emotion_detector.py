"""
情绪检测器
使用 FER 库或简化版检测
参考: face_recognition/emotion_detector.py
"""
import cv2
import numpy as np
from typing import List, Dict, Optional


class EmotionDetector:
    """
    情绪检测器
    支持 FER 库（更准确）和简化版（更快）
    """
    
    # 情绪标签
    EMOTIONS = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']
    
    # 情绪中文
    EMOTIONS_CN = {
        'Angry': '愤怒',
        'Disgust': '厌恶',
        'Fear': '恐惧',
        'Happy': '开心',
        'Sad': '悲伤',
        'Surprise': '惊讶',
        'Neutral': '平静'
    }
    
    def __init__(self, use_fer: bool = True):
        """
        初始化情绪检测器
        
        Args:
            use_fer: 是否使用 FER 库
        """
        self.use_fer = False
        self.fer_detector = None
        
        if use_fer:
            try:
                from fer import FER
                self.fer_detector = FER(mtcnn=False)  # mtcnn=False 更快
                self.use_fer = True
                print("情绪检测: 使用 FER 库")
            except ImportError:
                print("FER 未安装，使用简化版检测")
                print("安装命令: pip install fer")
        
        # Haar 级联（简化版需要）
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
    
    def detect(self, frame: np.ndarray, face: Dict = None) -> Optional[Dict]:
        """
        检测单个人脸的情绪
        
        Args:
            frame: 图像
            face: 人脸检测结果（可选）
            
        Returns:
            {'emotion': str, 'confidence': float, 'all_emotions': dict}
        """
        if frame is None:
            return None
        
        if self.use_fer and self.fer_detector:
            return self._detect_fer(frame, face)
        else:
            return self._detect_simple(frame, face)
    
    def detect_all(self, frame: np.ndarray) -> List[Dict]:
        """
        检测所有人脸的情绪
        
        Returns:
            情绪列表
        """
        if frame is None:
            return []
        
        if self.use_fer and self.fer_detector:
            return self._detect_fer_all(frame)
        else:
            return self._detect_simple_all(frame)
    
    def _detect_fer(self, frame: np.ndarray, face: Dict = None) -> Optional[Dict]:
        """使用 FER 检测"""
        try:
            if face:
                # 裁剪人脸区域
                x1, y1, x2, y2 = face['box']
                face_img = frame[y1:y2, x1:x2]
                emotions = self.fer_detector.detect_emotions(face_img)
            else:
                emotions = self.fer_detector.detect_emotions(frame)
            
            if emotions:
                emotion_scores = emotions[0]['emotions']
                top_emotion = max(emotion_scores, key=emotion_scores.get)
                
                return {
                    'emotion': top_emotion,
                    'confidence': emotion_scores[top_emotion],
                    'all_emotions': emotion_scores
                }
        except Exception as e:
            print(f"FER 检测错误: {e}")
        
        return None
    
    def _detect_fer_all(self, frame: np.ndarray) -> List[Dict]:
        """FER 检测所有人脸"""
        results = []
        
        try:
            emotions = self.fer_detector.detect_emotions(frame)
            
            for face_data in emotions:
                box = face_data['box']
                x, y, w, h = box
                emotion_scores = face_data['emotions']
                top_emotion = max(emotion_scores, key=emotion_scores.get)
                
                results.append({
                    'box': (x, y, x + w, y + h),
                    'emotion': top_emotion,
                    'confidence': emotion_scores[top_emotion],
                    'all_emotions': emotion_scores
                })
        except Exception as e:
            print(f"FER 检测错误: {e}")
        
        return results
    
    def _detect_simple(self, frame: np.ndarray, face: Dict = None) -> Optional[Dict]:
        """
        简化版检测
        基于简单的规则，准确度较低
        """
        # 简化版：返回 Neutral
        return {
            'emotion': 'Neutral',
            'confidence': 0.5,
            'all_emotions': {e: 0.0 for e in self.EMOTIONS}
        }
    
    def _detect_simple_all(self, frame: np.ndarray) -> List[Dict]:
        """简化版检测所有"""
        # 先检测人脸
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
        
        results = []
        for (x, y, w, h) in faces:
            results.append({
                'box': (x, y, x + w, y + h),
                'emotion': 'Neutral',
                'confidence': 0.5,
                'all_emotions': {e: 0.0 for e in self.EMOTIONS}
            })
        
        return results
    
    @classmethod
    def get_emotion_cn(cls, emotion: str) -> str:
        """获取情绪的中文名"""
        return cls.EMOTIONS_CN.get(emotion, emotion)
