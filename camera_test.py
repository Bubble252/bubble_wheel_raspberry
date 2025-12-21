import cv2
import sys

def main():
    print("尝试打开摄像头...")
    # 优先尝试 USB 摄像头 (当前在 video0)
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("无法打开索引 0，尝试索引 8...")
        cap = cv2.VideoCapture(8)
    
    # 如果索引 0 失败，尝试使用 libcamera 的 GStreamer 管道（如果安装了相关库）
    if not cap.isOpened():
        print("无法通过索引 0 打开摄像头。尝试使用 GStreamer...")
        gst_pipeline = "libcamerasrc ! video/x-raw, width=640, height=480, framerate=30/1 ! videoconvert ! appsink"
        cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)

    if not cap.isOpened():
        print("错误：无法打开摄像头。")
        print("请确保：")
        print("1. 摄像头排线连接正确（蓝带朝向网口/USB口，或者根据板子说明）。")
        print("2. 已经重启树莓派以加载驱动。")
        print("3. 尝试在终端运行 'rpicam-hello' 检查摄像头是否工作。")
        return

    print("摄像头已打开！按 'q' 键退出。")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("无法读取帧")
            break

        cv2.imshow('Camera Preview', frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
