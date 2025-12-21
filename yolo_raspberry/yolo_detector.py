"""
YOLOv8 ONNX 目标检测器
适用于树莓派
"""
import cv2
import numpy as np
import time

try:
    import onnxruntime as ort
    USE_ONNX = True
except ImportError:
    USE_ONNX = False
    print("警告: onnxruntime 未安装，将使用 OpenCV DNN")


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
        with open(classes_path, 'r', encoding='utf-8') as f:
            self.classes = [line.strip() for line in f.readlines()]
        
        self.conf_threshold = conf_threshold
        self.iou_threshold = iou_threshold
        
        # 加载模型
        print(f"加载模型: {model_path}")
        
        if USE_ONNX:
            self.session = ort.InferenceSession(
                model_path,
                providers=['CPUExecutionProvider']
            )
            self.input_name = self.session.get_inputs()[0].name
            self.input_type = self.session.get_inputs()[0].type
            self.input_shape = self.session.get_inputs()[0].shape
            self.input_height = self.input_shape[2]
            self.input_width = self.input_shape[3]
        else:
            self.net = cv2.dnn.readNetFromONNX(model_path)
            self.net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            self.net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            self.input_width = 640
            self.input_height = 640
            self.input_type = None
        
        print(f"模型输入尺寸: {self.input_width}x{self.input_height}")
        print(f"类别数量: {len(self.classes)}")
        
        # 生成颜色
        np.random.seed(42)
        self.colors = np.random.randint(0, 255, size=(len(self.classes), 3), dtype=np.uint8)
    
    def preprocess(self, image):
        """预处理图像"""
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
        
        # Convert to float16 if model expects it
        if self.input_type == 'tensor(float16)':
            input_img = input_img.astype(np.float16)
        
        return input_img
    
    def postprocess(self, outputs):
        """后处理检测结果"""
        # 检查输出形状以区分 YOLOv5 和 YOLOv8
        output = outputs[0]
        
        # YOLOv8: [1, 84, 8400] -> [8400, 84]
        if output.shape[1] == 84:
            predictions = output[0].T
            is_yolov5 = False
        # YOLOv5: [1, 25200, 85] -> [25200, 85]
        else:
            predictions = output[0]
            is_yolov5 = True
            
        boxes = []
        scores = []
        class_ids = []
        
        x_scale = self.orig_width / self.input_width
        y_scale = self.orig_height / self.input_height
        
        for pred in predictions:
            if is_yolov5:
                # YOLOv5: [x, y, w, h, obj_conf, class_scores...]
                obj_conf = pred[4]
                if obj_conf < self.conf_threshold:
                    continue
                class_scores = pred[5:]
                # 最终置信度 = obj_conf * class_score
                class_scores = class_scores * obj_conf
            else:
                # YOLOv8: [x, y, w, h, class_scores...]
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
            indices = cv2.dnn.NMSBoxes(boxes, scores, self.conf_threshold, self.iou_threshold)
            
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
    
    def detect(self, image):
        """执行检测"""
        input_img = self.preprocess(image)
        
        if USE_ONNX:
            outputs = self.session.run(None, {self.input_name: input_img})
        else:
            blob = cv2.dnn.blobFromImage(
                image, 1/255.0, (self.input_width, self.input_height),
                swapRB=True, crop=False
            )
            self.net.setInput(blob)
            outputs = [self.net.forward()]
        
        return self.postprocess(outputs)
    
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
        model_path="models/yolov5n.onnx",
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
        model_path="models/yolov5n.onnx",
        classes_path="models/coco_classes.txt",
        conf_threshold=0.5
    )
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    prev_time = time.time()
    
    print("按 'q' 退出")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        results = detector.detect(frame)
        frame = detector.draw_results(frame, results)
        
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
        detect_image(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        detect_camera()
