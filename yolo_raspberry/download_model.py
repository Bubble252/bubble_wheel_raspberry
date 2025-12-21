"""
下载 YOLO 模型脚本
"""
import urllib.request
import os
import sys

MODELS = {
    'yolov5n': 'https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5n.onnx',
    'yolov5s': 'https://github.com/ultralytics/yolov5/releases/download/v7.0/yolov5s.onnx',
    # YOLOv8 ONNX 官方不再直接提供下载，建议使用 YOLOv5n 或自行导出
}


def download_file(url, save_path):
    """下载文件并显示进度"""
    print(f"下载: {url}")
    print(f"保存到: {save_path}")
    
    def progress_hook(count, block_size, total_size):
        if total_size > 0:
            percent = int(count * block_size * 100 / total_size)
            sys.stdout.write(f"\r下载进度: {percent}%")
            sys.stdout.flush()
    
    try:
        urllib.request.urlretrieve(url, save_path, progress_hook)
        print("\n下载完成!")
        return True
    except Exception as e:
        print(f"\n下载失败: {e}")
        if os.path.exists(save_path):
            os.remove(save_path) # 删除失败的残留文件
        return False


def main():
    # 创建 models 目录
    os.makedirs("models", exist_ok=True)
    
    print("可用模型:")
    print("  1. yolov5n (推荐，稳定且快速)")
    print("  2. yolov5s (精度稍高)")
    print("  注意: YOLOv8n ONNX 官方未直接提供，本项目默认使用 YOLOv5n")
    print()
    
    choice = input("选择模型 (1-2，默认1): ").strip() or "1"
    
    model_map = {'1': 'yolov5n', '2': 'yolov5s'}
    model_name = model_map.get(choice, 'yolov5n')
    
    url = MODELS[model_name]
    save_path = f"models/{model_name}.onnx"
    
    if os.path.exists(save_path):
        overwrite = input(f"{save_path} 已存在，是否覆盖? (y/n): ").strip().lower()
        if overwrite != 'y':
            print("取消下载")
            return
    
    success = download_file(url, save_path)
    
    if success:
        # 如果不是 yolov8n，创建软链接或复制提示
        if model_name != 'yolov8n':
            print(f"\n注意: 默认使用 yolov8n.onnx")
            print(f"如果要使用 {model_name}，请修改代码中的模型路径")
            print(f"或重命名: mv models/{model_name}.onnx models/yolov8n.onnx")


if __name__ == "__main__":
    main()
