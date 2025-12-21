"""
人脸识别器 - 身份识别
使用 OpenCV LBPH 算法
"""
import cv2
import numpy as np
import os
import pickle


class FaceRecognizer:
    def __init__(self, known_faces_dir="known_faces/", model_path="models/"):
        """
        初始化人脸识别器
        
        Args:
            known_faces_dir: 已知人脸图片目录
            model_path: 模型保存目录
        """
        self.known_faces_dir = known_faces_dir
        self.model_path = model_path
        
        # Haar 级联检测器
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # LBPH 人脸识别器
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        
        self.label_map = {}  # id -> name
        self.is_trained = False
        
        # 创建必要的目录
        os.makedirs(known_faces_dir, exist_ok=True)
        os.makedirs(model_path, exist_ok=True)
    
    def train_from_directory(self):
        """从目录加载已知人脸并训练"""
        faces = []
        labels = []
        label_id = 0
        
        if not os.path.exists(self.known_faces_dir):
            print(f"目录不存在: {self.known_faces_dir}")
            return False
        
        for person_name in os.listdir(self.known_faces_dir):
            person_dir = os.path.join(self.known_faces_dir, person_name)
            if not os.path.isdir(person_dir):
                continue
            
            self.label_map[label_id] = person_name
            person_faces = 0
            
            for img_name in os.listdir(person_dir):
                if not img_name.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    continue
                    
                img_path = os.path.join(person_dir, img_name)
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                
                if img is None:
                    continue
                
                # 检测人脸
                detected = self.face_cascade.detectMultiScale(img, 1.1, 5)
                
                for (x, y, w, h) in detected:
                    face_roi = img[y:y+h, x:x+w]
                    face_roi = cv2.resize(face_roi, (100, 100))
                    faces.append(face_roi)
                    labels.append(label_id)
                    person_faces += 1
            
            print(f"  {person_name}: {person_faces} 张人脸")
            label_id += 1
        
        if len(faces) > 0:
            self.recognizer.train(faces, np.array(labels))
            self.is_trained = True
            print(f"\n训练完成！共 {len(self.label_map)} 人，{len(faces)} 张图片")
            return True
        else:
            print("没有找到训练数据！")
            print(f"请在 {self.known_faces_dir} 下创建以人名命名的文件夹，并放入照片")
            return False
    
    def recognize(self, frame):
        """
        识别人脸身份
        
        Returns:
            list: 包含 {'box': tuple, 'name': str, 'confidence': float} 的列表
        """
        if not self.is_trained:
            return []
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, 1.1, 5, minSize=(30, 30))
        
        results = []
        for (x, y, w, h) in faces:
            face_roi = gray[y:y+h, x:x+w]
            face_roi = cv2.resize(face_roi, (100, 100))
            
            label, confidence = self.recognizer.predict(face_roi)
            
            # LBPH confidence 越小越好，阈值通常设为 70-100
            if confidence < 80:
                name = self.label_map.get(label, "Unknown")
            else:
                name = "Unknown"
            
            results.append({
                'box': (x, y, x + w, y + h),
                'name': name,
                'confidence': confidence
            })
        
        return results
    
    def save_model(self, filename="face_model"):
        """保存模型"""
        model_file = os.path.join(self.model_path, f"{filename}.yml")
        labels_file = os.path.join(self.model_path, f"{filename}.labels")
        
        self.recognizer.save(model_file)
        with open(labels_file, "wb") as f:
            pickle.dump(self.label_map, f)
        
        print(f"模型已保存: {model_file}")
    
    def load_model(self, filename="face_model"):
        """加载模型"""
        model_file = os.path.join(self.model_path, f"{filename}.yml")
        labels_file = os.path.join(self.model_path, f"{filename}.labels")
        
        if not os.path.exists(model_file):
            print(f"模型文件不存在: {model_file}")
            return False
        
        self.recognizer.read(model_file)
        with open(labels_file, "rb") as f:
            self.label_map = pickle.load(f)
        
        self.is_trained = True
        print(f"模型已加载，共 {len(self.label_map)} 人")
        return True
    
    def draw_results(self, frame, results):
        """绘制识别结果"""
        for r in results:
            x1, y1, x2, y2 = r['box']
            name = r['name']
            
            # 已知人脸用绿色，未知用红色
            color = (0, 255, 0) if name != "Unknown" else (0, 0, 255)
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
            
            label = f"{name} ({r['confidence']:.0f})"
            cv2.putText(frame, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        
        return frame


def capture_faces(person_name, num_photos=10):
    """采集人脸照片"""
    save_dir = f"known_faces/{person_name}"
    os.makedirs(save_dir, exist_ok=True)
    
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
    )
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    count = 0
    print(f"采集 {person_name} 的人脸照片")
    print(f"按 SPACE 拍照，ESC 退出")
    
    while count < num_photos:
        ret, frame = cap.read()
        if not ret:
            break
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)
        
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
        
        cv2.putText(frame, f"Photos: {count}/{num_photos}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, "Press SPACE to capture", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        cv2.imshow("Capture Faces", frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == 27:  # ESC
            break
        elif key == 32 and len(faces) > 0:  # SPACE
            photo_path = os.path.join(save_dir, f"{count+1}.jpg")
            cv2.imwrite(photo_path, frame)
            print(f"保存: {photo_path}")
            count += 1
    
    cap.release()
    cv2.destroyAllWindows()
    print(f"采集完成！共 {count} 张照片保存到 {save_dir}")


def main():
    """测试人脸识别"""
    import time
    import sys
    
    # 检查命令行参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "capture":
            name = sys.argv[2] if len(sys.argv) > 2 else input("请输入姓名: ")
            capture_faces(name)
            return
        elif sys.argv[1] == "train":
            recognizer = FaceRecognizer()
            recognizer.train_from_directory()
            recognizer.save_model()
            return
    
    # 默认：运行识别
    recognizer = FaceRecognizer()
    
    # 尝试加载模型，否则训练
    if not recognizer.load_model():
        print("尝试从目录训练...")
        if recognizer.train_from_directory():
            recognizer.save_model()
        else:
            print("\n使用方法:")
            print("  1. 采集人脸: python face_recognizer.py capture 姓名")
            print("  2. 训练模型: python face_recognizer.py train")
            print("  3. 运行识别: python face_recognizer.py")
            return
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    prev_time = time.time()
    
    print("\n人脸识别启动，按 'q' 退出")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        results = recognizer.recognize(frame)
        frame = recognizer.draw_results(frame, results)
        
        # FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("Face Recognition", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
