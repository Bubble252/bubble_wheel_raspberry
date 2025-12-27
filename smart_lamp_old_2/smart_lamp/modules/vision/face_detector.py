"""
人脸检测器
使用 OpenCV DNN 或 Haar 级联检测器
参考: face_recognition/face_detector.py
"""
import cv2
import numpy as np
import os
from typing import List, Dict, Optional


class FaceDetector:
    """
    人脸检测器
    支持 DNN (更准确) 和 Haar (更快) 两种模式
    """
    
    def __init__(self, model_path: str = "models/", confidence_threshold: float = 0.5):
        """
        初始化人脸检测器
        
        Args:
            model_path: 模型文件目录
            confidence_threshold: 置信度阈值
        """
        self.confidence_threshold = confidence_threshold
        self.use_dnn = False
        self.net = None
        self.face_cascade = None
        
        # 尝试加载 DNN 模型
        prototxt = os.path.join(model_path, "deploy.prototxt")
        caffemodel = os.path.join(model_path, "res10_300x300_ssd_iter_140000.caffemodel")
        
        if os.path.exists(prototxt) and os.path.exists(caffemodel):
            try:
                self.net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
                self.use_dnn = True
                print("人脸检测: 使用 DNN 模型")
            except Exception as e:
                print(f"DNN 模型加载失败: {e}")
        
        # 回退到 Haar 级联
        if not self.use_dnn:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            print("人脸检测: 使用 Haar 级联")
    
    def detect(self, frame: np.ndarray) -> List[Dict]:
        """
        检测人脸
        
        Args:
            frame: BGR 或 RGB 图像
            
        Returns:
            人脸列表，每个元素为 {'box': (x1, y1, x2, y2), 'confidence': float}
        """
        if frame is None:
            return []
        
        if self.use_dnn:
            return self._detect_dnn(frame)
        else:
            return self._detect_haar(frame)
    
    def _detect_dnn(self, frame: np.ndarray) -> List[Dict]:
        """DNN 检测"""
        h, w = frame.shape[:2]
        
        # 预处理
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)),
            1.0,
            (300, 300),
            (104.0, 177.0, 123.0)
        )
        
        self.net.setInput(blob)
        detections = self.net.forward()
        
        faces = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            
            if confidence > self.confidence_threshold:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (x1, y1, x2, y2) = box.astype("int")
                
                # 边界检查
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(w, x2)
                y2 = min(h, y2)
                
                if x2 > x1 and y2 > y1:
                    faces.append({
                        'box': (x1, y1, x2, y2),
                        'confidence': float(confidence)
                    })
        
        return faces
    
    def _detect_haar(self, frame: np.ndarray) -> List[Dict]:
        """Haar 级联检测"""
        # 转灰度
        if len(frame.shape) == 3:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        else:
            gray = frame
        
        # 检测
        detections = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(30, 30)
        )
        
        faces = []
        for (x, y, w, h) in detections:
            faces.append({
                'box': (x, y, x + w, y + h),
                'confidence': 1.0  # Haar 不提供置信度
            })
        
        return faces
    
    def detect_largest(self, frame: np.ndarray) -> Optional[Dict]:
        """
        检测最大的人脸
        
        Returns:
            最大的人脸，或 None
        """
        faces = self.detect(frame)
        
        if not faces:
            return None
        
        # 按面积排序
        def face_area(face):
            x1, y1, x2, y2 = face['box']
            return (x2 - x1) * (y2 - y1)
        
        return max(faces, key=face_area)
    
    def get_face_roi(self, frame: np.ndarray, face: Dict, padding: float = 0.2) -> Optional[np.ndarray]:
        """
        获取人脸区域图像
        
        Args:
            frame: 原图
            face: 人脸检测结果
            padding: 边缘扩展比例
            
        Returns:
            人脸区域图像
        """
        x1, y1, x2, y2 = face['box']
        h, w = frame.shape[:2]
        
        # 扩展边界
        pad_w = int((x2 - x1) * padding)
        pad_h = int((y2 - y1) * padding)
        
        x1 = max(0, x1 - pad_w)
        y1 = max(0, y1 - pad_h)
        x2 = min(w, x2 + pad_w)
        y2 = min(h, y2 + pad_h)
        
        return frame[y1:y2, x1:x2]
