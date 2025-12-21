"""
下载人脸检测模型
"""
import urllib.request
import os
import sys

MODELS = {
    'deploy.prototxt': 'https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt',
    'res10_300x300_ssd_iter_140000.caffemodel': 'https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20170830/res10_300x300_ssd_iter_140000.caffemodel'
}


def download_file(url, save_path):
    """下载文件"""
    print(f"下载: {url}")
    print(f"保存到: {save_path}")
    
    def progress_hook(count, block_size, total_size):
        if total_size > 0:
            percent = int(count * block_size * 100 / total_size)
            sys.stdout.write(f"\r下载进度: {percent}%")
            sys.stdout.flush()
    
    try:
        urllib.request.urlretrieve(url, save_path, progress_hook)
        print("\n完成!")
        return True
    except Exception as e:
        print(f"\n下载失败: {e}")
        return False


def main():
    # 创建目录
    os.makedirs("models", exist_ok=True)
    
    print("下载人脸检测模型...")
    print("=" * 50)
    
    for filename, url in MODELS.items():
        save_path = os.path.join("models", filename)
        
        if os.path.exists(save_path):
            print(f"跳过 {filename} (已存在)")
            continue
        
        success = download_file(url, save_path)
        if not success:
            print(f"警告: 无法下载 {filename}")
            print("可以手动下载后放入 models/ 目录")
    
    print("\n下载完成！")
    print("模型文件位于: models/")


if __name__ == "__main__":
    main()
