"""
动物专用检测器
基于 YOLO，只检测动物类别
"""
import cv2
import numpy as np
import time
from yolo_detector import YOLODetector

# COCO 数据集中的动物类别 (class_id: name)
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

# 中文名称
ANIMAL_NAMES_CN = {
    'bird': '鸟',
    'cat': '猫',
    'dog': '狗',
    'horse': '马',
    'sheep': '羊',
    'cow': '牛',
    'elephant': '大象',
    'bear': '熊',
    'zebra': '斑马',
    'giraffe': '长颈鹿'
}


class AnimalDetector:
    def __init__(self, model_path="models/yolov8n.onnx", 
                 classes_path="models/coco_classes.txt",
                 conf_threshold=0.5):
        """
        初始化动物检测器
        """
        self.detector = YOLODetector(model_path, classes_path, conf_threshold)
        self.animal_ids = set(ANIMAL_CLASSES.keys())
        
        # 动物专用颜色
        self.animal_colors = {
            14: (255, 200, 0),    # bird - 蓝色
            15: (0, 165, 255),    # cat - 橙色
            16: (0, 255, 255),    # dog - 黄色
            17: (139, 69, 19),    # horse - 棕色
            18: (255, 255, 255),  # sheep - 白色
            19: (0, 0, 0),        # cow - 黑色
            20: (128, 128, 128),  # elephant - 灰色
            21: (0, 100, 0),      # bear - 深绿
            22: (255, 255, 255),  # zebra - 白色
            23: (0, 215, 255),    # giraffe - 金色
        }
    
    def detect_animals(self, image):
        """只检测动物"""
        all_results = self.detector.detect(image)
        
        # 过滤只保留动物
        animal_results = [
            r for r in all_results 
            if r['class_id'] in self.animal_ids
        ]
        
        return animal_results
    
    def draw_results(self, image, results, show_chinese=False):
        """绘制检测结果"""
        for r in results:
            x1, y1, x2, y2 = r['box']
            class_id = r['class_id']
            
            color = self.animal_colors.get(class_id, (0, 255, 0))
            
            # 绘制边界框
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
            
            # 标签
            if show_chinese:
                label = f"{ANIMAL_NAMES_CN.get(r['class_name'], r['class_name'])}: {r['confidence']:.2f}"
            else:
                label = f"{r['class_name']}: {r['confidence']:.2f}"
            
            (label_w, label_h), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2
            )
            cv2.rectangle(image, (x1, y1 - label_h - 10), 
                         (x1 + label_w, y1), color, -1)
            cv2.putText(image, label, (x1, y1 - 5),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return image


def main():
    """实时检测动物"""
    detector = AnimalDetector(
        model_path="models/yolov8n.onnx",
        classes_path="models/coco_classes.txt",
        conf_threshold=0.4
    )
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开摄像头")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    prev_time = time.time()
    
    print("动物检测器启动")
    print("可检测: 鸟、猫、狗、马、羊、牛、大象、熊、斑马、长颈鹿")
    print("按 'q' 退出")
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        results = detector.detect_animals(frame)
        frame = detector.draw_results(frame, results)
        
        # FPS
        curr_time = time.time()
        fps = 1 / (curr_time - prev_time)
        prev_time = curr_time
        
        # 显示信息
        cv2.putText(frame, f"FPS: {fps:.1f}", (10, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"Animals: {len(results)}", (10, 60),
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        
        # 显示检测到的动物名称
        y = 90
        for r in results:
            cv2.putText(frame, f"- {r['class_name']}", (10, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2)
            y += 25
        
        cv2.imshow("Animal Detection", frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
