"""
亮度调节模式
通过识别手的开合程度来控制亮度
"""
import time
from typing import Optional, Tuple
from .base_mode import BaseMode


class BrightnessMode(BaseMode):
    """
    亮度调节模式
    
    功能：
    - 固定舵机当前位置
    - 检测手部开合程度
    - 映射到亮度值 (0.0 - 1.0)
    - 实时调节LED亮度
    
    手势说明：
    - 手掌张开 = 最亮 (1.0)
    - 握拳 = 最暗 (0.0)
    - 中间状态 = 对应亮度
    """
    
    MODE_NAME = "亮度调节"
    
    def __init__(self, controller):
        super().__init__(controller)
        
        # 手部检测相关
        self._hand_detector = None
        self._mp_hands = None
        
        # 亮度控制
        self._current_brightness = 0.5
        self._target_brightness = 0.5
        self._smooth_factor = 0.2  # 平滑系数
        
        # 检测状态
        self._no_hand_count = 0
        self._no_hand_threshold = 15
        self._last_openness: Optional[float] = None
        
        # 固定舵机位置
        self._servo_locked = False
    
    def on_enter(self):
        """进入模式：初始化检测器，锁定舵机"""
        # 初始化 MediaPipe Hands
        try:
            import mediapipe as mp
            self._mp_hands = mp.solutions.hands
            self._hand_detector = self._mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=1,
                min_detection_confidence=0.7,
                min_tracking_confidence=0.5
            )
            self._print("MediaPipe Hands 初始化成功")
        except ImportError:
            self._print("警告: MediaPipe 未安装，使用模拟模式")
            self._hand_detector = None
        
        # 锁定舵机当前位置
        self._lock_servos()
        
        # 获取当前亮度
        if self.controller:
            lighting = getattr(self.controller, '_lighting', None)
            if lighting:
                self._current_brightness = lighting.current_brightness
        
        self._print(f"当前亮度: {self._current_brightness:.0%}")
        self._print("张开手掌调亮，握拳调暗")
    
    def on_exit(self):
        """退出模式：释放资源"""
        if self._hand_detector:
            self._hand_detector.close()
            self._hand_detector = None
        
        self._print(f"最终亮度: {self._current_brightness:.0%}")
    
    def _lock_servos(self):
        """锁定舵机当前位置"""
        if self.controller:
            servo_thread = getattr(self.controller, '_servo_thread', None)
            if servo_thread:
                # 读取当前位置并保持
                servo_thread.hold_position()
                self._servo_locked = True
                self._debug("舵机位置已锁定")
    
    def update(self, frame=None, voice_text: str = None) -> bool:
        """
        更新模式
        
        Args:
            frame: 摄像头帧
            voice_text: 语音文本
            
        Returns:
            是否继续运行
        """
        if frame is None:
            return True
        
        # 检测手部开合程度
        openness = self._detect_hand_openness(frame)
        
        if openness is not None:
            self._no_hand_count = 0
            self._last_openness = openness
            
            # 映射到亮度
            self._target_brightness = openness
            
            # 平滑更新亮度
            self._current_brightness += self._smooth_factor * (
                self._target_brightness - self._current_brightness
            )
            self._current_brightness = max(0.0, min(1.0, self._current_brightness))
            
            # 设置亮度
            self._set_brightness(self._current_brightness)
            
            self._debug(f"手部开合: {openness:.2f} -> 亮度: {self._current_brightness:.0%}")
        else:
            self._no_hand_count += 1
            if self._no_hand_count == self._no_hand_threshold:
                self._print("未检测到手部")
        
        return True
    
    def _detect_hand_openness(self, frame) -> Optional[float]:
        """
        检测手部开合程度
        
        Args:
            frame: BGR图像
            
        Returns:
            开合程度 (0.0=握拳, 1.0=张开)，None表示未检测到
        """
        if self._hand_detector is None:
            return None
        
        import cv2
        import math
        
        # BGR -> RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # 检测
        results = self._hand_detector.process(rgb)
        
        if not results.multi_hand_landmarks:
            return None
        
        # 取第一只手
        hand = results.multi_hand_landmarks[0]
        landmarks = hand.landmark
        
        # 计算开合程度
        # 方法：计算指尖到手掌中心的平均距离
        
        # 手掌中心（手腕和中指根部的中点）
        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        palm_center = (
            (wrist.x + middle_mcp.x) / 2,
            (wrist.y + middle_mcp.y) / 2
        )
        
        # 五个指尖的索引
        fingertips = [4, 8, 12, 16, 20]
        
        # 计算指尖到手掌中心的平均距离
        total_dist = 0
        for tip_idx in fingertips:
            tip = landmarks[tip_idx]
            dist = math.sqrt(
                (tip.x - palm_center[0]) ** 2 +
                (tip.y - palm_center[1]) ** 2
            )
            total_dist += dist
        
        avg_dist = total_dist / len(fingertips)
        
        # 归一化到 0-1
        # 经验值：握拳时约 0.1，张开时约 0.35
        min_dist = 0.08
        max_dist = 0.35
        
        openness = (avg_dist - min_dist) / (max_dist - min_dist)
        openness = max(0.0, min(1.0, openness))
        
        return openness
    
    def _set_brightness(self, brightness: float):
        """
        设置亮度
        
        Args:
            brightness: 亮度值 (0.0 - 1.0)
        """
        if not self.controller:
            return
        
        lighting = getattr(self.controller, '_lighting', None)
        if lighting:
            lighting.set(brightness)
    
    def handle_voice(self, text: str) -> bool:
        """处理语音命令"""
        if '最亮' in text or '全亮' in text:
            self._current_brightness = 1.0
            self._set_brightness(1.0)
            self._print("亮度: 100%")
            return True
        
        if '最暗' in text or '关灯' in text:
            self._current_brightness = 0.0
            self._set_brightness(0.0)
            self._print("亮度: 0%")
            return True
        
        if '一半' in text or '中等' in text:
            self._current_brightness = 0.5
            self._set_brightness(0.5)
            self._print("亮度: 50%")
            return True
        
        return False


# ==================== 独立测试 ====================
def test_brightness_mode():
    """独立测试亮度调节模式"""
    import cv2
    
    print("=" * 50)
    print("亮度调节模式 - 独立测试")
    print("=" * 50)
    print("张开手掌 = 亮，握拳 = 暗")
    print("按 'q' 退出测试")
    print()
    
    # 创建模拟控制器
    class MockController:
        def __init__(self):
            self.debug = True
            self._servo_thread = None
            self._lighting = MockLighting()
    
    class MockLighting:
        def __init__(self):
            self.current_brightness = 0.5
        
        def set(self, brightness):
            self.current_brightness = brightness
            # 用进度条显示亮度
            bar_len = 30
            filled = int(bar_len * brightness)
            bar = '█' * filled + '░' * (bar_len - filled)
            print(f"\r亮度: [{bar}] {brightness:.0%}  ", end='', flush=True)
    
    controller = MockController()
    mode = BrightnessMode(controller)
    
    # 打开摄像头
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("错误: 无法打开摄像头")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # 进入模式
    mode.enter()
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 更新模式
            mode.update(frame=frame)
            
            # 显示画面
            brightness = mode._current_brightness
            
            # 绘制亮度条
            bar_height = int(frame.shape[0] * brightness)
            cv2.rectangle(frame, (10, frame.shape[0] - bar_height), 
                         (30, frame.shape[0]), (0, 255, 255), -1)
            cv2.rectangle(frame, (10, 0), (30, frame.shape[0]), (128, 128, 128), 2)
            
            # 显示数值
            cv2.putText(frame, f"Brightness: {brightness:.0%}", (50, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            if mode._last_openness is not None:
                cv2.putText(frame, f"Hand Openness: {mode._last_openness:.2f}", 
                           (50, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            
            cv2.putText(frame, "Press 'q' to quit", 
                       (10, frame.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow("Brightness Mode Test", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    finally:
        print()  # 换行
        mode.exit()
        cap.release()
        cv2.destroyAllWindows()
        print("\n测试结束")


if __name__ == "__main__":
    test_brightness_mode()
