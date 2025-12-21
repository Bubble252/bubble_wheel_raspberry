"""
情绪检测器
使用 FER 库或简化版检测
"""
import cv2
import numpy as np
import os


class EmotionDetector:
    # 情绪标签
    EMOTIONS = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']
    
    # 情绪对应的中文
    EMOTIONS_CN = {
        'Angry': '愤怒',
        'Disgust': '厌恶', 
        'Fear': '恐惧',
        'Happy': '开心',
        'Sad': '悲伤',
        'Surprise': '惊讶',
        'Neutral': '平静'
    }
    
    # 情绪对应的颜色
    EMOTION_COLORS = {
        'Angry': (0, 0, 255),      # 红色
        'Disgust': (0, 100, 0),    # 深绿
        'Fear': (128, 0, 128),     # 紫色
        'Happy': (0, 255, 255),    # 黄色
        'Sad': (255, 0, 0),        # 蓝色
        'Surprise': (0, 165, 255), # 橙色
        'Neutral': (128, 128, 128) # 灰色
    }
    
    def __init__(self, use_fer=True):
        """
        初始化情绪检测器
        
        Args:
            use_fer: 是否使用 FER 库（更准确但更慢）
        """
        # 人脸检测器
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        self.fer_detector = None
        self.use_fer = False
        
        if use_fer:
            try:
                try:
                    from fer import FER
                except ImportError:
                    from fer.fer import FER
                    
                self.fer_detector = FER(mtcnn=False)  # mtcnn=False 更快
                self.use_fer = True
                print("使用 FER 库进行情绪检测")
            except ImportError:
                print("FER 未安装，使用简化版检测")
                print("安装 FER: pip install fer")
    
    def detect_emotion(self, frame):
        """
        检测情绪
        
        Returns:
            list: 包含 {'box': tuple, 'emotion': str, 'confidence': float, 'all_emotions': dict} 的列表
        """
        if self.use_fer and self.fer_detector:
            return self._detect_fer(frame)
        else:
            return self._detect_simple(frame)
    
    def _detect_fer(self, frame):
        """使用 FER 库检测"""
        results = []
        
        try:
            emotions = self.fer_detector.detect_emotions(frame)
            
            for face in emotions:
                box = face['box']
                x, y, w, h = box
                emotion_scores = face['emotions']
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
    
    def _detect_simple(self, frame):
        """简化版：只检测人脸，不识别具体情绪"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
        
        results = []
        for (x, y, w, h) in faces:
            results.append({
                'box': (x, y, x + w, y + h),
                'emotion': 'Unknown',
                'confidence': 0.0,
                'all_emotions': {}
            })
        
        return results
    
    def draw_results(self, frame, results, show_chinese=False, show_all=False):
        """
        绘制检测结果
        
        Args:
            frame: 图像
            results: 检测结果
            show_chinese: 显示中文
            show_all: 显示所有情绪得分
        """
        for r in results:
            x1, y1, x2, y2 = r['box']
            emotion = r['emotion']
            
            color = self.EMOTION_COLORS.get(emotion, (0, 255, 0))
            
            # 绘制边界框
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # 标签
            if show_chinese:
                label = self.EMOTIONS_CN.get(emotion, emotion)
            else:
                label = emotion
            
            label = f"{label}: {r['confidence']:.2f}"
            cv2.putText(frame, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
            
            # 显示所有情绪得分
            if show_all and r['all_emotions']:
                y_offset = y2 + 20
                for emo, score in sorted(r['all_emotions'].items(), 
                                        key=lambda x: x[1], reverse=True):
                    emo_color = self.EMOTION_COLORS.get(emo, (255, 255, 255))
                    text = f"{emo}: {score:.2f}"
                    cv2.putText(frame, text, (x1, y_offset),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.4, emo_color, 1)
                    y_offset += 15
        
        return frame


def main():
    """测试情绪检测"""
    import time
    
    detector = EmotionDetector(use_fer=True)
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    prev_time = time.time()
    show_all = False
    
    print("情绪检测启动")
    print("按 'a' 切换显示所有情绪得分")
    print("按 'q' 退出")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        results = detector.detect_emotion(frame)
        frame = detector.draw_results(frame, results, show_all=show_all)
        
        # FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("Emotion Detection", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('a'):
            show_all = not show_all
            print(f"显示所有情绪: {'开' if show_all else '关'}")
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
