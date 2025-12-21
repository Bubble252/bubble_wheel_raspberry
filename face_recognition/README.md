# 树莓派人脸识别 + 情绪检测 + 身份识别 教程

## 📋 项目概述

本项目实现以下功能：
1. **人脸检测** - 检测画面中的人脸
2. **情绪识别** - 识别表情（开心、悲伤、愤怒、惊讶等）
3. **身份识别** - 根据已有照片库识别人物身份

---

## 🔧 技术选型

| 功能 | 推荐库 | 树莓派兼容性 | 说明 |
|------|--------|-------------|------|
| 人脸检测 | OpenCV Haar/DNN | ✅ 优秀 | 轻量快速 |
| 人脸识别 | face_recognition | ⚠️ 一般 | 需要编译dlib |
| 情绪检测 | FER / DeepFace | ⚠️ 较重 | 建议用轻量模型 |

### 推荐方案
- **树莓派4 (4GB+)**: 可以本地运行全部功能
- **树莓派3/Zero**: 建议只做检测，识别交给服务器

---

## 📦 第一步：系统准备

### 1.1 更新系统
```bash
sudo apt update
sudo apt upgrade -y
```

### 1.2 安装系统依赖
```bash
# 基础依赖
sudo apt install -y python3-pip python3-venv

# OpenCV 依赖
sudo apt install -y libatlas-base-dev libjasper-dev libqtgui4 libqt4-test
sudo apt install -y libhdf5-dev libhdf5-serial-dev
sudo apt install -y libharfbuzz0b libwebp6 libtiff5 libjasper1 libilmbase23 libopenexr23
sudo apt install -y libavcodec-dev libavformat-dev libswscale-dev libv4l-dev
sudo apt install -y libxvidcore-dev libx264-dev

# 摄像头支持
sudo apt install -y libcamera-dev libcamera-apps
```

### 1.3 创建虚拟环境
```bash
cd ~
mkdir face_project
cd face_project
python3 -m venv venv
source venv/bin/activate
```

---

## 📦 第二步：安装 Python 依赖

### 2.1 安装 OpenCV
```bash
pip install opencv-python-headless
# 或者如果需要GUI显示：
# pip install opencv-python
```

### 2.2 安装 NumPy
```bash
pip install numpy
```

### 2.3 安装 face_recognition（可选，较慢）

> ⚠️ 这一步在树莓派上可能需要 1-2 小时，建议使用 screen 或 tmux

```bash
# 先安装 dlib 依赖
sudo apt install -y cmake libopenblas-dev liblapack-dev

# 安装 dlib（编译很慢）
pip install dlib

# 安装 face_recognition
pip install face_recognition
```

**如果 dlib 安装失败，使用预编译版本：**
```bash
# 方案B：使用轻量替代方案
pip install opencv-python-headless
# 用 OpenCV 的 DNN 人脸检测代替
```

### 2.4 安装情绪检测库
```bash
# 轻量方案（推荐）
pip install fer

# 或者使用 tensorflow-lite（更适合树莓派）
pip install tflite-runtime
```

---

## 📦 第三步：下载模型文件

### 3.1 创建模型目录
```bash
mkdir -p ~/face_project/models
cd ~/face_project/models
```

### 3.2 下载人脸检测模型（OpenCV DNN）
```bash
# Caffe 模型（推荐，更快）
wget https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt
wget https://raw.githubusercontent.com/opencv/opencv_3rdparty/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel
```

### 3.3 下载情绪检测模型
```bash
# FER 会自动下载，或手动下载：
wget https://github.com/oarriaga/face_classification/raw/master/trained_models/emotion_models/fer2013_mini_XCEPTION.102-0.66.hdf5
```

---

## 📝 第四步：创建代码文件

### 4.1 基础人脸检测 `face_detector.py`

```python
import cv2
import numpy as np

class FaceDetector:
    def __init__(self, model_path="models/"):
        # 加载 OpenCV DNN 人脸检测模型
        prototxt = model_path + "deploy.prototxt"
        caffemodel = model_path + "res10_300x300_ssd_iter_140000.caffemodel"
        self.net = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
        self.confidence_threshold = 0.5
    
    def detect_faces(self, frame):
        """检测人脸，返回边界框列表"""
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
                faces.append({
                    'box': (x1, y1, x2, y2),
                    'confidence': float(confidence)
                })
        return faces


if __name__ == "__main__":
    detector = FaceDetector()
    cap = cv2.VideoCapture(0)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        faces = detector.detect_faces(frame)
        
        for face in faces:
            x1, y1, x2, y2 = face['box']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{face['confidence']:.2f}", 
                       (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        cv2.imshow("Face Detection", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
    
    cap.release()
    cv2.destroyAllWindows()
```

### 4.2 人脸识别（身份识别）`face_recognizer.py`

```python
import cv2
import numpy as np
import os
import pickle

class FaceRecognizer:
    def __init__(self, known_faces_dir="known_faces/", model_path="models/"):
        # 人脸检测器
        prototxt = model_path + "deploy.prototxt"
        caffemodel = model_path + "res10_300x300_ssd_iter_140000.caffemodel"
        self.detector = cv2.dnn.readNetFromCaffe(prototxt, caffemodel)
        
        # 人脸识别器 (使用 OpenCV 的 LBPH)
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        
        self.known_faces_dir = known_faces_dir
        self.label_map = {}  # id -> name
        self.is_trained = False
    
    def train_from_directory(self):
        """从目录加载已知人脸并训练"""
        faces = []
        labels = []
        label_id = 0
        
        for person_name in os.listdir(self.known_faces_dir):
            person_dir = os.path.join(self.known_faces_dir, person_name)
            if not os.path.isdir(person_dir):
                continue
            
            self.label_map[label_id] = person_name
            
            for img_name in os.listdir(person_dir):
                img_path = os.path.join(person_dir, img_name)
                img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
                if img is not None:
                    # 检测人脸
                    face_cascade = cv2.CascadeClassifier(
                        cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
                    )
                    detected = face_cascade.detectMultiScale(img, 1.1, 5)
                    for (x, y, w, h) in detected:
                        face_roi = img[y:y+h, x:x+w]
                        face_roi = cv2.resize(face_roi, (100, 100))
                        faces.append(face_roi)
                        labels.append(label_id)
            
            label_id += 1
        
        if len(faces) > 0:
            self.recognizer.train(faces, np.array(labels))
            self.is_trained = True
            print(f"训练完成！共 {len(self.label_map)} 人，{len(faces)} 张图片")
        else:
            print("没有找到训练数据！")
    
    def recognize(self, frame):
        """识别人脸身份"""
        if not self.is_trained:
            return []
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        faces = face_cascade.detectMultiScale(gray, 1.1, 5)
        
        results = []
        for (x, y, w, h) in faces:
            face_roi = gray[y:y+h, x:x+w]
            face_roi = cv2.resize(face_roi, (100, 100))
            
            label, confidence = self.recognizer.predict(face_roi)
            name = self.label_map.get(label, "Unknown")
            
            # confidence 越小越好，阈值通常设为 70-100
            if confidence < 80:
                results.append({
                    'box': (x, y, x+w, y+h),
                    'name': name,
                    'confidence': confidence
                })
            else:
                results.append({
                    'box': (x, y, x+w, y+h),
                    'name': "Unknown",
                    'confidence': confidence
                })
        
        return results
    
    def save_model(self, path="face_model.yml"):
        """保存模型"""
        self.recognizer.save(path)
        with open(path + ".labels", "wb") as f:
            pickle.dump(self.label_map, f)
    
    def load_model(self, path="face_model.yml"):
        """加载模型"""
        self.recognizer.read(path)
        with open(path + ".labels", "rb") as f:
            self.label_map = pickle.load(f)
        self.is_trained = True


if __name__ == "__main__":
    recognizer = FaceRecognizer()
    
    # 训练（首次运行）
    # 需要先在 known_faces/ 目录下按人名创建子目录，放入照片
    # known_faces/
    #   ├── 张三/
    #   │   ├── 1.jpg
    #   │   ├── 2.jpg
    #   ├── 李四/
    #   │   ├── 1.jpg
    
    recognizer.train_from_directory()
    recognizer.save_model()
    
    cap = cv2.VideoCapture(0)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        results = recognizer.recognize(frame)
        
        for r in results:
            x1, y1, x2, y2 = r['box']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            cv2.putText(frame, f"{r['name']}", 
                       (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        cv2.imshow("Face Recognition", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
    
    cap.release()
    cv2.destroyAllWindows()
```

### 4.3 情绪检测 `emotion_detector.py`

```python
import cv2
import numpy as np

class EmotionDetector:
    def __init__(self, model_path="models/"):
        # 使用 OpenCV DNN 加载情绪模型
        # 或者使用 FER 库
        self.emotions = ['Angry', 'Disgust', 'Fear', 'Happy', 'Sad', 'Surprise', 'Neutral']
        
        # 使用 Haar 级联做人脸检测（更轻量）
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        
        # 尝试加载情绪模型
        self.use_fer = False
        try:
            from fer import FER
            self.fer_detector = FER(mtcnn=False)  # mtcnn=False 更快
            self.use_fer = True
            print("使用 FER 库进行情绪检测")
        except ImportError:
            print("FER 未安装，使用简化版情绪检测")
    
    def detect_emotion(self, frame):
        """检测情绪"""
        results = []
        
        if self.use_fer:
            # 使用 FER 库
            emotions = self.fer_detector.detect_emotions(frame)
            for face in emotions:
                box = face['box']
                x, y, w, h = box
                emotion_scores = face['emotions']
                top_emotion = max(emotion_scores, key=emotion_scores.get)
                
                results.append({
                    'box': (x, y, x+w, y+h),
                    'emotion': top_emotion,
                    'confidence': emotion_scores[top_emotion],
                    'all_emotions': emotion_scores
                })
        else:
            # 简化版：只检测人脸，不识别具体情绪
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5)
            
            for (x, y, w, h) in faces:
                results.append({
                    'box': (x, y, x+w, y+h),
                    'emotion': 'Unknown',
                    'confidence': 0.0
                })
        
        return results


if __name__ == "__main__":
    detector = EmotionDetector()
    cap = cv2.VideoCapture(0)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        results = detector.detect_emotion(frame)
        
        for r in results:
            x1, y1, x2, y2 = r['box']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            text = f"{r['emotion']}: {r['confidence']:.2f}"
            cv2.putText(frame, text, (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        cv2.imshow("Emotion Detection", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
    
    cap.release()
    cv2.destroyAllWindows()
```

### 4.4 综合应用 `main.py`

```python
import cv2
import time
from face_detector import FaceDetector
from face_recognizer import FaceRecognizer
from emotion_detector import EmotionDetector

def main():
    # 初始化检测器
    face_detector = FaceDetector()
    face_recognizer = FaceRecognizer()
    emotion_detector = EmotionDetector()
    
    # 加载已训练的人脸模型（如果有）
    try:
        face_recognizer.load_model()
        print("已加载人脸识别模型")
    except:
        print("未找到人脸模型，将只进行检测")
    
    cap = cv2.VideoCapture(0)
    prev_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # 1. 检测人脸
        faces = face_detector.detect_faces(frame)
        
        # 2. 识别身份
        identities = face_recognizer.recognize(frame)
        
        # 3. 检测情绪
        emotions = emotion_detector.detect_emotion(frame)
        
        # 绘制结果
        for face in faces:
            x1, y1, x2, y2 = face['box']
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        
        for identity in identities:
            x1, y1, x2, y2 = identity['box']
            cv2.putText(frame, identity['name'], (x1, y1-30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        
        for emotion in emotions:
            x1, y1, x2, y2 = emotion['box']
            cv2.putText(frame, emotion['emotion'], (x1, y1-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        
        # 计算 FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
        
        cv2.imshow("Face Recognition System", frame)
        if cv2.waitKey(1) & 0xFF == 27:
            break
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
```

---

## 📁 第五步：准备人脸照片库

### 5.1 创建目录结构
```bash
mkdir -p ~/face_project/known_faces/张三
mkdir -p ~/face_project/known_faces/李四
# 为每个人创建一个目录
```

### 5.2 添加照片
```bash
# 将每个人的照片（3-10张）放入对应目录
# 建议：正脸、侧脸、不同光线各几张
```

### 5.3 训练模型
```bash
cd ~/face_project
source venv/bin/activate
python face_recognizer.py
# 会自动训练并保存模型
```

---

## 🚀 第六步：运行

```bash
cd ~/face_project
source venv/bin/activate

# 单独测试人脸检测
python face_detector.py

# 单独测试情绪检测
python emotion_detector.py

# 单独测试人脸识别
python face_recognizer.py

# 运行完整系统
python main.py
```

---

## ⚠️ 常见问题

### Q1: ImportError: libcblas.so.3
```bash
sudo apt install libatlas-base-dev
```

### Q2: 摄像头无法打开
```bash
# 检查摄像头
ls /dev/video*

# 如果使用树莓派官方摄像头
sudo raspi-config
# 启用 Legacy Camera 或 libcamera
```

### Q3: FER 安装失败
```bash
# 使用 tensorflow-lite 替代
pip install tflite-runtime
# 然后使用轻量版情绪检测
```

### Q4: 内存不足
```bash
# 增加 swap
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# 修改 CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

---

## 📊 性能预期

| 树莓派型号 | 人脸检测 | 人脸识别 | 情绪检测 |
|-----------|---------|---------|---------|
| Pi 4 (4GB) | 15-20 FPS | 10-15 FPS | 5-10 FPS |
| Pi 4 (2GB) | 10-15 FPS | 8-10 FPS | 3-5 FPS |
| Pi 3B+ | 5-8 FPS | 3-5 FPS | 1-3 FPS |

---

## 📚 扩展阅读

- [OpenCV 人脸检测文档](https://docs.opencv.org/master/df/d6c/tutorial_face_main.html)
- [face_recognition 库](https://github.com/ageitgey/face_recognition)
- [FER 情绪识别](https://github.com/justinshenk/fer)
