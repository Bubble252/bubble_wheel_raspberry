# 树莓派 YOLO 目标检测教程

## 📋 项目概述

本项目在树莓派上实现 YOLO 目标检测，能够识别：
- 80+ 类物体（人、车、动物、家具等）
- 实时视频流检测
- 支持图片检测

---

## 🔧 技术选型

| 方案 | 速度 | 精度 | 树莓派兼容性 | 推荐度 |
|------|------|------|-------------|--------|
| **YOLOv5n (ONNX)** | ⭐⭐⭐ | ⭐⭐ | ✅ 优秀 | ⭐⭐⭐⭐⭐ |
| **YOLOv8n (ONNX)** | ⭐⭐⭐ | ⭐⭐⭐ | ✅ 优秀 | ⭐⭐⭐⭐⭐ |
| YOLOv5n (PyTorch) | ⭐⭐ | ⭐⭐ | ⚠️ 较慢 | ⭐⭐⭐ |
| YOLOv8n (TensorRT) | ⭐⭐⭐⭐ | ⭐⭐⭐ | ❌ 不支持 | - |
| TensorFlow Lite | ⭐⭐⭐⭐ | ⭐⭐ | ✅ 优秀 | ⭐⭐⭐⭐ |

### 推荐方案
- **首选**: YOLOv8n + ONNX Runtime（平衡速度和精度）
- **备选**: YOLOv5n + OpenCV DNN（更简单）

---

## 📦 第一步：系统准备

### 1.1 更新系统
```bash
sudo apt update
sudo apt upgrade -y
```

### 1.2 安装系统依赖
```bash
# 基础工具
sudo apt install -y python3-pip python3-venv git

# OpenCV 依赖
sudo apt install -y libatlas-base-dev libhdf5-dev
sudo apt install -y libavcodec-dev libavformat-dev libswscale-dev
sudo apt install -y libjpeg-dev libpng-dev libtiff-dev

# 摄像头支持
sudo apt install -y libcamera-dev
```

### 1.3 增加 Swap（推荐）
```bash
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# 修改 CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon
```

### 1.4 创建项目目录
```bash
cd ~
mkdir yolo_project
cd yolo_project
python3 -m venv venv
source venv/bin/activate
```

---

## 📦 第二步：安装 Python 依赖

### 2.1 升级 pip
```bash
pip install --upgrade pip
```

### 2.2 安装核心依赖
```bash
# NumPy（先装，确保兼容性）
pip install numpy

# OpenCV
pip install opencv-python-headless
# 如果需要GUI显示：pip install opencv-python
```

### 2.3 安装 ONNX Runtime（推荐）
```bash
# 树莓派 ARM64 版本
pip install onnxruntime
```

### 2.4 安装其他依赖
```bash
pip install pillow
pip install requests  # 用于下载模型
```

---

## 📦 第三步：下载 YOLO 模型

### 3.1 创建模型目录
```bash
mkdir -p ~/yolo_project/models
cd ~/yolo_project/models
```

### 3.2 下载 YOLOv8n ONNX 模型
```bash
# 方法1：使用 wget 直接下载
wget https://github.com/ultralytics/assets/releases/download/v0.0.0/yolov8n.onnx

# 方法2：如果网络不好，可以在 PC 上下载后传输
# PC 上下载：https://github.com/ultralytics/assets/releases
# 然后用 scp 传输：
# scp yolov8n.onnx pi@raspberrypi:~/yolo_project/models/
```

### 3.3 下载 COCO 类别标签
```bash
cat > coco_classes.txt << 'EOF'
person
bicycle
car
motorcycle
airplane
bus
train
truck
boat
traffic light
fire hydrant
stop sign
parking meter
bench
bird
cat
dog
horse
sheep
cow
elephant
bear
zebra
giraffe
backpack
umbrella
handbag
tie
suitcase
frisbee
skis
snowboard
sports ball
kite
baseball bat
baseball glove
skateboard
surfboard
tennis racket
bottle
wine glass
cup
fork
knife
spoon
bowl
banana
apple
sandwich
orange
broccoli
carrot
hot dog
pizza
donut
cake
chair
couch
potted plant
bed
dining table
toilet
tv
laptop
mouse
remote
keyboard
cell phone
microwave
oven
toaster
sink
refrigerator
book
clock
vase
scissors
teddy bear
hair drier
toothbrush
EOF
```

---

## 📝 第四步：创建检测代码

### 4.1 YOLOv8 ONNX 检测器 `yolo_detector.py`

```python
import cv2
import numpy as np
import onnxruntime as ort
import time

class YOLODetector:
    def __init__(self, model_path, classes_path, conf_threshold=0.5, iou_threshold=0.45):
        """
        初始化 YOLO 检测器
        
        Args:
            model_path: ONNX 模型路径
            classes_path: 类别标签文件路径
            conf_threshold: 置信度阈值
            iou_threshold: NMS IOU 阈值
        """
        # 加载类别
        with open(classes_path, 'r') as f:
            self.classes = [line.strip() for line in f.readlines()]
        
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        
        # 加载 ONNX 模型
        print(f"加载模型: {model_path}")
        self.session = ort.InferenceSession(
            model_path,
            providers=['CPUExecutionProvider']
        )
        
        # 获取输入输出信息
        self.input_name = self.session.get_inputs()[0].name
        self.input_shape = self.session.get_inputs()[0].shape
        self.input_height = self.input_shape[2]
        self.input_width = self.input_shape[3]
        
        print(f"模型输入尺寸: {self.input_width}x{self.input_height}")
        print(f"类别数量: {len(self.classes)}")
        
        # 生成颜色
        np.random.seed(42)
        self.colors = np.random.randint(0, 255, size=(len(self.classes), 3), dtype=np.uint8)
    
    def preprocess(self, image):
        """预处理图像"""
        # 保存原始尺寸
        self.orig_height, self.orig_width = image.shape[:2]
        
        # Resize
        input_img = cv2.resize(image, (self.input_width, self.input_height))
        
        # BGR -> RGB
        input_img = cv2.cvtColor(input_img, cv2.COLOR_BGR2RGB)
        
        # Normalize to [0, 1]
        input_img = input_img.astype(np.float32) / 255.0
        
        # HWC -> CHW
        input_img = input_img.transpose(2, 0, 1)
        
        # Add batch dimension
        input_img = np.expand_dims(input_img, axis=0)
        
        return input_img
    
    def postprocess(self, outputs):
        """后处理检测结果"""
        # YOLOv8 输出格式: [1, 84, 8400]
        # 84 = 4 (bbox) + 80 (classes)
        predictions = outputs[0][0].T  # [8400, 84]
        
        boxes = []
        scores = []
        class_ids = []
        
        # 计算缩放比例
        x_scale = self.orig_width / self.input_width
        y_scale = self.orig_height / self.input_height
        
        for pred in predictions:
            # 获取类别置信度
            class_scores = pred[4:]
            max_score = np.max(class_scores)
            
            if max_score >= self.conf_threshold:
                class_id = np.argmax(class_scores)
                
                # 获取边界框 (center_x, center_y, width, height)
                cx, cy, w, h = pred[:4]
                
                # 转换为 (x1, y1, x2, y2)
                x1 = int((cx - w / 2) * x_scale)
                y1 = int((cy - h / 2) * y_scale)
                x2 = int((cx + w / 2) * x_scale)
                y2 = int((cy + h / 2) * y_scale)
                
                boxes.append([x1, y1, x2 - x1, y2 - y1])  # OpenCV NMS 格式
                scores.append(float(max_score))
                class_ids.append(int(class_id))
        
        # NMS
        if len(boxes) > 0:
            indices = cv2.dnn.NMSBoxes(boxes, scores, self.conf_threshold, self.iou_threshold)
            
            results = []
            for i in indices:
                idx = i[0] if isinstance(i, (list, np.ndarray)) else i
                x, y, w, h = boxes[idx]
                results.append({
                    'box': (x, y, x + w, y + h),
                    'class_id': class_ids[idx],
                    'class_name': self.classes[class_ids[idx]],
                    'confidence': scores[idx]
                })
            return results
        
        return []
    
    def detect(self, image):
        """执行检测"""
        # 预处理
        input_img = self.preprocess(image)
        
        # 推理
        outputs = self.session.run(None, {self.input_name: input_img})
        
        # 后处理
        results = self.postprocess(outputs)
        
        return results
    
    def draw_results(self, image, results):
        """绘制检测结果"""
        for r in results:
            x1, y1, x2, y2 = r['box']
            class_id = r['class_id']
            color = tuple(int(c) for c in self.colors[class_id])
            
            # 绘制边界框
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            
            # 绘制标签
            label = f"{r['class_name']}: {r['confidence']:.2f}"
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
            )
            cv2.rectangle(image, (x1, y1 - label_h - 10), 
                         (x1 + label_w, y1), color, -1)
            cv2.putText(image, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        return image


def detect_image(image_path, output_path=None):
    """检测单张图片"""
    detector = YOLODetector(
        model_path="models/yolov8n.onnx",
        classes_path="models/coco_classes.txt"
    )
    
    image = cv2.imread(image_path)
    if image is None:
        print(f"无法读取图片: {image_path}")
        return
    
    start = time.time()
    results = detector.detect(image)
    elapsed = time.time() - start
    
    print(f"检测耗时: {elapsed*1000:.1f}ms")
    print(f"检测到 {len(results)} 个物体:")
    for r in results:
        print(f"  - {r['class_name']}: {r['confidence']:.2f}")
    
    # 绘制结果
    image = detector.draw_results(image, results)
    
    if output_path:
        cv2.imwrite(output_path, image)
        print(f"结果保存到: {output_path}")
    else:
        cv2.imshow("Detection", image)
        cv2.waitKey(0)
        cv2.destroyAllWindows()


def detect_camera():
    """实时摄像头检测"""
    detector = YOLODetector(
        model_path="models/yolov8n.onnx",
        classes_path="models/coco_classes.txt",
        conf_threshold=0.5
    )
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    # 降低分辨率以提高帧率
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    prev_time = time.time()
    
    print("按 'q' 退出")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        # 检测
        results = detector.detect(frame)
        
        # 绘制结果
        frame = detector.draw_results(frame, results)
        
        # 计算 FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"Objects: {len(results)}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("YOLO Detection", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 检测图片
        detect_image(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        # 实时摄像头检测
        detect_camera()
```

### 4.2 简化版（使用 OpenCV DNN）`yolo_opencv.py`

```python
import cv2
import numpy as np
import time

class YOLOOpenCV:
    """使用 OpenCV DNN 模块加载 YOLO"""
    
    def __init__(self, model_path, classes_path, conf_threshold=0.5, nms_threshold=0.45):
        # 加载类别
        with open(classes_path, 'r') as f:
            self.classes = [line.strip() for line in f.readlines()]
        
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        
        # 加载模型
        print(f"加载模型: {model_path}")
        self.net = cv2.dnn.readNetFromONNX(model_path)
        self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
        
        # 生成颜色
        np.random.seed(42)
        self.colors = np.random.randint(0, 255, size=(len(self.classes), 3), dtype=np.uint8)
        
        print("模型加载完成")
    
    def detect(self, image):
        """执行检测"""
        height, width = image.shape[:2]
        
        # 创建 blob
        blob = cv2.dnn.blobFromImage(
            image, 1/255.0, (640, 640), 
            swapRB=True, crop=False
        )
        
        self.net.setInput(blob)
        outputs = self.net.forward()
        
        # 后处理
        return self._postprocess(outputs, width, height)
    
    def _postprocess(self, outputs, orig_width, orig_height):
        """后处理"""
        predictions = outputs[0].T  # [8400, 84]
        
        boxes = []
        scores = []
        class_ids = []
        
        x_scale = orig_width / 640
        y_scale = orig_height / 640
        
        for pred in predictions:
            class_scores = pred[4:]
            max_score = np.max(class_scores)
            
            if max_score >= self.conf_threshold:
                class_id = np.argmax(class_scores)
                cx, cy, w, h = pred[:4]
                
                x1 = int((cx - w / 2) * x_scale)
                y1 = int((cy - h / 2) * y_scale)
                x2 = int((cx + w / 2) * x_scale)
                y2 = int((cy + h / 2) * y_scale)
                
                boxes.append([x1, y1, x2 - x1, y2 - y1])
                scores.append(float(max_score))
                class_ids.append(int(class_id))
        
        # NMS
        results = []
        if len(boxes) > 0:
            indices = cv2.dnn.NMSBoxes(boxes, scores, self.conf_threshold, self.nms_threshold)
            
            for i in indices:
                idx = i[0] if isinstance(i, (list, np.ndarray)) else i
                x, y, w, h = boxes[idx]
                results.append({
                    'box': (x, y, x + w, y + h),
                    'class_id': class_ids[idx],
                    'class_name': self.classes[class_ids[idx]],
                    'confidence': scores[idx]
                })
        
        return results
    
    def draw(self, image, results):
        """绘制结果"""
        for r in results:
            x1, y1, x2, y2 = r['box']
            color = tuple(int(c) for c in self.colors[r['class_id']])
            
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            label = f"{r['class_name']}: {r['confidence']:.2f}"
            cv2.putText(image, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
        
        return image


if __name__ == "__main__":
    detector = YOLOOpenCV(
        model_path="models/yolov8n.onnx",
        classes_path="models/coco_classes.txt"
    )
    
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    prev_time = time.time()
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        results = detector.detect(frame)
        frame = detector.draw(frame, results)
        
        # FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("YOLO", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
```

### 4.3 动物专用检测器 `animal_detector.py`

```python
import cv2
import numpy as np
from yolo_detector import YOLODetector

# COCO 数据集中的动物类别
ANIMAL_CLASSES = {
    14: 'bird',
    15: 'cat', 
    16: 'dog',
    17: 'horse',
    18: 'sheep',
    19: 'cow',
    20: 'elephant',
    21: 'bear',
    22: 'zebra',
    23: 'giraffe'
}

class AnimalDetector:
    def __init__(self, model_path, classes_path):
        self.detector = YOLODetector(model_path, classes_path)
        self.animal_ids = set(ANIMAL_CLASSES.keys())
    
    def detect_animals(self, image):
        """只检测动物"""
        all_results = self.detector.detect(image)
        
        # 过滤只保留动物
        animal_results = [
            r for r in all_results 
            if r['class_id'] in self.animal_ids
        ]
        
        return animal_results
    
    def draw(self, image, results):
        return self.detector.draw_results(image, results)


if __name__ == "__main__":
    detector = AnimalDetector(
        model_path="models/yolov8n.onnx",
        classes_path="models/coco_classes.txt"
    )
    
    cap = cv2.VideoCapture(0)
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        results = detector.detect_animals(frame)
        frame = detector.draw(frame, results)
        
        cv2.putText(frame, f"Animals: {len(results)}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        cv2.imshow("Animal Detection", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()
```

---

## 🚀 第五步：运行测试

### 5.1 测试模型加载
```bash
cd ~/yolo_project
source venv/bin/activate

python -c "
import onnxruntime as ort
sess = ort.InferenceSession('models/yolov8n.onnx')
print('模型加载成功!')
print('输入:', sess.get_inputs()[0].shape)
"
```

### 5.2 检测图片
```bash
# 下载测试图片
wget -O test.jpg https://ultralytics.com/images/zidane.jpg

# 运行检测
python yolo_detector.py test.jpg output.jpg
```

### 5.3 实时摄像头检测
```bash
python yolo_detector.py
# 按 'q' 退出
```

### 5.4 只检测动物
```bash
python animal_detector.py
```

---

## ⚙️ 第六步：性能优化

### 6.1 降低分辨率
```python
# 修改 yolo_detector.py
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
```

### 6.2 跳帧检测
```python
frame_count = 0
skip_frames = 2  # 每3帧检测1次

while True:
    ret, frame = cap.read()
    frame_count += 1
    
    if frame_count % (skip_frames + 1) == 0:
        results = detector.detect(frame)
    
    # 绘制上一次的结果
    frame = detector.draw(frame, results)
```

### 6.3 使用更小的模型
```bash
# 下载 YOLOv8n 的精简版
# 或者使用 YOLOv5n（更小更快）
wget https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.onnx
```

---

## ⚠️ 常见问题

### Q1: ONNX Runtime 安装失败
```bash
# 尝试指定版本
pip install onnxruntime==1.15.0

# 或使用 OpenCV DNN 替代
# 改用 yolo_opencv.py
```

### Q2: 摄像头无法打开
```bash
# 检查摄像头
ls /dev/video*

# 尝试不同的设备号
cap = cv2.VideoCapture(1)

# 树莓派官方摄像头
# 使用 libcamera
```

### Q3: 内存不足 (Killed)
```bash
# 增加 swap
sudo dphys-swapfile swapoff
sudo nano /etc/dphys-swapfile
# CONF_SWAPSIZE=2048
sudo dphys-swapfile setup
sudo dphys-swapfile swapon

# 或使用更小的模型
```

### Q4: 检测速度太慢
```bash
# 1. 降低输入分辨率
# 2. 跳帧检测
# 3. 使用 YOLOv5n 代替 YOLOv8n
# 4. 考虑使用 Coral USB 加速器
```

---

## 📊 性能预期

| 树莓派型号 | YOLOv8n (640x640) | YOLOv5n (640x640) | 降分辨率 (320x320) |
|-----------|-------------------|-------------------|-------------------|
| Pi 4 (4GB) | 2-3 FPS | 3-4 FPS | 5-8 FPS |
| Pi 4 (2GB) | 1-2 FPS | 2-3 FPS | 4-6 FPS |
| Pi 3B+ | <1 FPS | 1-2 FPS | 2-3 FPS |

---

## 📁 项目结构

```
yolo_project/
├── venv/                    # Python 虚拟环境
├── models/
│   ├── yolov8n.onnx        # YOLO 模型
│   └── coco_classes.txt    # 类别标签
├── yolo_detector.py        # 主检测器（ONNX Runtime）
├── yolo_opencv.py          # OpenCV DNN 版本
├── animal_detector.py      # 动物专用检测器
└── README.md               # 本文档
```

---

## 📚 扩展阅读

- [YOLOv8 官方文档](https://docs.ultralytics.com/)
- [ONNX Runtime](https://onnxruntime.ai/)
- [OpenCV DNN 模块](https://docs.opencv.org/master/d2/d58/tutorial_table_of_content_dnn.html)
- [树莓派摄像头配置](https://www.raspberrypi.com/documentation/accessories/camera.html)

---

## 🔗 可检测的物体类别（COCO 80类）

| 类别 | 中文 | 类别 | 中文 |
|------|------|------|------|
| person | 人 | bicycle | 自行车 |
| car | 汽车 | motorcycle | 摩托车 |
| airplane | 飞机 | bus | 公交车 |
| train | 火车 | truck | 卡车 |
| boat | 船 | traffic light | 红绿灯 |
| bird | 鸟 | cat | 猫 |
| dog | 狗 | horse | 马 |
| sheep | 羊 | cow | 牛 |
| elephant | 大象 | bear | 熊 |
| zebra | 斑马 | giraffe | 长颈鹿 |
| backpack | 背包 | umbrella | 雨伞 |
| bottle | 瓶子 | cup | 杯子 |
| chair | 椅子 | couch | 沙发 |
| tv | 电视 | laptop | 笔记本电脑 |
| cell phone | 手机 | book | 书 |
| ... | ... | ... | ... |
