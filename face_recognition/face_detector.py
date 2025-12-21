"""
人脸检测器 - 使用 OpenCV DNN
适用于树莓派
"""
import cv2
import numpy as np
import os

class FaceDetector:
    def __init__(self, model_path="models/", confidence_threshold=0.5):
        """
        初始化人脸检测器
        
        Args:
            model_path: 模型文件目录
            confidence_threshold: 置信度阈值
        """
        prototxt = os.path.join(model_path, "deploy.prototxt")
        caffemodel = os.path.join(model_path, "res10_300x300_ssd_iter_140000.caffemodel")
        
        # 检查模型文件
        if not os.path.exists(prototxt) or not os.path.exists(caffemodel):
            print("模型文件不存在，使用 Haar 级联检测器")
            self.use_dnn = False
            self.face_cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            )
        else:
            print("使用 DNN 人脸检测器")
            self.use_dnn = True
            self.net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
        
        self.confidence_threshold = confidence_threshold
    
    def detect_faces(self, frame):
        """
        检测人脸
        
        Returns:
            list: 包含 {'box': (x1, y1, x2, y2), 'confidence': float} 的列表
        """
        if self.use_dnn:
            return self._detect_dnn(frame)
        else:
            return self._detect_haar(frame)
    
    def _detect_dnn(self, frame):
        """使用 DNN 检测"""
        h, w = frame.shape[:2]
        blob = cv2.dnn.blobFromImage(
            cv2.resize(frame, (300, 300)), 
            1.0, (300, 300), (104.0, 177.0, 123.0)
        )
        self.net.setInput(blob)
        detections = self.net.forward()
        
        faces = []
        for i in range(detections.shape[2]):
            confidence = detections[0, 0, i, 2]
            if confidence > self.confidence_threshold:
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (x1, y1, x2, y2) = box.astype("int")
                
                # 确保坐标在图像范围内
                x1 = max(0, x1)
                y1 = max(0, y1)
                x2 = min(w, x2)
                y2 = min(h, y2)
                
                faces.append({
                    'box': (x1, y1, x2, y2),
                    'confidence': float(confidence)
                })
        return faces
    
    def _detect_haar(self, frame):
        """使用 Haar 级联检测"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        detections = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
        )
        
        faces = []
        for (x, y, w, h) in detections:
            faces.append({
                'box': (x, y, x + w, y + h),
                'confidence': 1.0  # Haar 不返回置信度
            })
        return faces
    
    def draw_faces(self, frame, faces):
        """绘制检测结果"""
        for face in faces:
            x1, y1, x2, y2 = face['box']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            
            label = f"Face: {face['confidence']:.2f}"
            cv2.putText(frame, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        return frame


def main():
    """测试人脸检测"""
    import time
    
    detector = FaceDetector()
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    prev_time = time.time()
    
    print("人脸检测启动，按 'q' 退出")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        faces = detector.detect_faces(frame)
        frame = detector.draw_faces(frame, faces)
        
        # FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"Faces: {len(faces)}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("Face Detection", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
