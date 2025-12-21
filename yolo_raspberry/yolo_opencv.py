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