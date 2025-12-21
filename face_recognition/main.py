"""
综合应用 - 人脸检测 + 身份识别 + 情绪检测
"""
import cv2
import time
import os
from face_detector import FaceDetector
from face_recognizer import FaceRecognizer
from emotion_detector import EmotionDetector


class FaceAnalyzer:
    """人脸综合分析器"""
    
    def __init__(self, enable_recognition=True, enable_emotion=True):
        """
        初始化
        
        Args:
            enable_recognition: 启用身份识别
            enable_emotion: 启用情绪检测
        """
        print("初始化人脸分析器...")
        
        # 人脸检测器
        self.face_detector = FaceDetector()
        
        # 身份识别
        self.enable_recognition = enable_recognition
        if enable_recognition:
            self.face_recognizer = FaceRecognizer()
            if not self.face_recognizer.load_model():
                print("未找到识别模型，尝试训练...")
                if self.face_recognizer.train_from_directory():
                    self.face_recognizer.save_model()
                else:
                    print("无法训练模型，禁用身份识别")
                    self.enable_recognition = False
        
        # 情绪检测
        self.enable_emotion = enable_emotion
        if enable_emotion:
            self.emotion_detector = EmotionDetector(use_fer=True)
        
        print("初始化完成！")
    
    def analyze(self, frame):
        """
        分析人脸
        
        Returns:
            list: 包含每个人脸的完整分析结果
        """
        results = []
        
        # 1. 检测人脸
        faces = self.face_detector.detect_faces(frame)
        
        # 2. 身份识别
        identities = []
        if self.enable_recognition:
            identities = self.face_recognizer.recognize(frame)
        
        # 3. 情绪检测
        emotions = []
        if self.enable_emotion:
            emotions = self.emotion_detector.detect_emotion(frame)
        
        # 合并结果
        for face in faces:
            result = {
                'box': face['box'],
                'face_confidence': face['confidence'],
                'name': 'Unknown',
                'name_confidence': 0,
                'emotion': 'Unknown',
                'emotion_confidence': 0
            }
            
            # 匹配身份
            for identity in identities:
                if self._boxes_overlap(face['box'], identity['box']):
                    result['name'] = identity['name']
                    result['name_confidence'] = identity['confidence']
                    break
            
            # 匹配情绪
            for emotion in emotions:
                if self._boxes_overlap(face['box'], emotion['box']):
                    result['emotion'] = emotion['emotion']
                    result['emotion_confidence'] = emotion['confidence']
                    result['all_emotions'] = emotion.get('all_emotions', {})
                    break
            
            results.append(result)
        
        return results
    
    def _boxes_overlap(self, box1, box2, threshold=0.5):
        """检查两个框是否重叠"""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
        # 计算交集
        x1_i = max(x1_1, x1_2)
        y1_i = max(y1_1, y1_2)
        x2_i = min(x2_1, x2_2)
        y2_i = min(y2_1, y2_2)
        
        if x2_i < x1_i or y2_i < y1_i:
            return False
        
        area_i = (x2_i - x1_i) * (y2_i - y1_i)
        area_1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area_2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        
        iou = area_i / min(area_1, area_2)
        return iou > threshold
    
    def draw_results(self, frame, results):
        """绘制分析结果"""
        for r in results:
            x1, y1, x2, y2 = r['box']
            
            # 颜色：已知人脸绿色，未知红色
            if r['name'] != 'Unknown':
                color = (0, 255, 0)
            else:
                color = (0, 0, 255)
            
            # 绘制边界框
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            # 姓名
            cv2.putText(frame, r['name'], (x1, y1 - 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
            
            # 情绪
            emotion_color = EmotionDetector.EMOTION_COLORS.get(
                r['emotion'], (255, 255, 255)
            )
            cv2.putText(frame, r['emotion'], (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, emotion_color, 2)
        
        return frame


def main():
    """运行综合分析"""
    import sys
    
    # 检查参数
    enable_recognition = '--no-recognition' not in sys.argv
    enable_emotion = '--no-emotion' not in sys.argv
    
    print("=" * 50)
    print("人脸综合分析系统")
    print("=" * 50)
    print(f"身份识别: {'启用' if enable_recognition else '禁用'}")
    print(f"情绪检测: {'启用' if enable_emotion else '禁用'}")
    print()
    
    analyzer = FaceAnalyzer(
        enable_recognition=enable_recognition,
        enable_emotion=enable_emotion
    )
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    prev_time = time.time()
    
    print("\n按 'q' 退出")
    print("按 's' 截图")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        results = analyzer.analyze(frame)
        frame = analyzer.draw_results(frame, results)
        
        # FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        
        # 信息面板
        cv2.rectangle(frame, (5, 5), (200, 80), (0, 0, 0), -1)
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        cv2.putText(frame, f"Faces: {len(results)}", (10, 50),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # 显示检测到的人
        y = 75
        for r in results:
            info = f"{r['name']}: {r['emotion']}"
            cv2.putText(frame, info, (10, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            y += 20
        
        cv2.imshow("Face Analysis", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            filename = f"screenshot_{int(time.time())}.jpg"
            cv2.imwrite(filename, frame)
            print(f"截图保存: {filename}")
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
