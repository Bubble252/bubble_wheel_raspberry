"""
手部跟随模式
借鉴 hand_pose_demo_zeroMQ.py 的算法
获取手部 position, euler, openness
"""
import cv2
import math
import numpy as np
from typing import Optional, Tuple, Dict, Any
from .base_mode import BaseMode


# ========== 手部检测器（内嵌版本）==========
OPERATOR2MANO_RIGHT = np.array([[0, 0, -1], [-1, 0, 0], [0, 1, 0]])
OPERATOR2MANO_LEFT = np.array([[0, 0, -1], [1, 0, 0], [0, -1, 0]])


def compute_hand_openness(joint_pos, eps=1e-6):
    """计算手掌张开程度"""
    if joint_pos is None:
        return None, None
    palm_center = np.mean(joint_pos[[0, 5, 9, 13, 17]], axis=0)
    fingertips = joint_pos[[4, 8, 12, 16, 20]]
    distances = np.linalg.norm(fingertips - palm_center, axis=1)
    palm_width = np.linalg.norm(joint_pos[5] - joint_pos[17])
    denom = palm_width if palm_width >= eps else max(np.max(distances), eps)
    openness = float(np.clip(np.mean(distances) / denom, 0.0, 3.0))
    return openness, distances


def detect_pointing_one(joint_pos, eps=1e-6):
    """
    检测"比1"手势（食指伸直，其他手指弯曲）
    
    MediaPipe 关键点:
    - 4: 拇指尖, 8: 食指尖, 12: 中指尖, 16: 无名指尖, 20: 小指尖
    - 0: 手腕, 5: 食指根, 9: 中指根, 13: 无名指根, 17: 小指根
    
    Returns:
        bool: 是否为"比1"手势
    """
    if joint_pos is None:
        return False
    
    # 计算手掌宽度作为参考
    palm_width = np.linalg.norm(joint_pos[5] - joint_pos[17])
    if palm_width < eps:
        return False
    
    # 计算各手指指尖到手腕的距离（归一化）
    wrist = joint_pos[0]
    
    # 食指伸直：指尖到手腕距离 > 指根到手腕距离 * 1.3
    index_tip_dist = np.linalg.norm(joint_pos[8] - wrist)
    index_mcp_dist = np.linalg.norm(joint_pos[5] - wrist)
    index_extended = index_tip_dist > index_mcp_dist * 1.3
    
    # 其他手指弯曲：指尖到手腕距离 < 指根到手腕距离 * 1.2
    # 中指
    middle_tip_dist = np.linalg.norm(joint_pos[12] - wrist)
    middle_mcp_dist = np.linalg.norm(joint_pos[9] - wrist)
    middle_bent = middle_tip_dist < middle_mcp_dist * 1.2
    
    # 无名指
    ring_tip_dist = np.linalg.norm(joint_pos[16] - wrist)
    ring_mcp_dist = np.linalg.norm(joint_pos[13] - wrist)
    ring_bent = ring_tip_dist < ring_mcp_dist * 1.2
    
    # 小指
    pinky_tip_dist = np.linalg.norm(joint_pos[20] - wrist)
    pinky_mcp_dist = np.linalg.norm(joint_pos[17] - wrist)
    pinky_bent = pinky_tip_dist < pinky_mcp_dist * 1.2
    
    # 拇指（可以伸直或弯曲，不强制要求）
    
    return index_extended and middle_bent and ring_bent and pinky_bent


class EmbeddedSingleHandDetector:
    """内嵌的单手检测器（基于 MediaPipe）"""
    
    def __init__(self, hand_type="Right", min_detection_confidence=0.8,
                 min_tracking_confidence=0.8, selfie=False,
                 use_pose=False, real_palm_width=0.085):
        import mediapipe as mp
        
        self.mp = mp
        self.hand_detector = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )
        self.use_pose = use_pose
        self.real_palm_width = real_palm_width
        self.selfie = selfie
        self.operator2mano = OPERATOR2MANO_RIGHT if hand_type == "Right" else OPERATOR2MANO_LEFT
        inverse_hand_dict = {"Right": "Left", "Left": "Right"}
        self.detected_hand_type = hand_type if selfie else inverse_hand_dict[hand_type]

    @staticmethod
    def parse_keypoint_3d(keypoint_3d) -> np.ndarray:
        keypoint = np.empty([21, 3], dtype=np.float32)
        for i in range(21):
            keypoint[i, 0] = keypoint_3d.landmark[i].x
            keypoint[i, 1] = keypoint_3d.landmark[i].y
            keypoint[i, 2] = keypoint_3d.landmark[i].z
        return keypoint

    @staticmethod
    def estimate_frame_from_hand_points(keypoint_3d_array: np.ndarray) -> np.ndarray:
        assert keypoint_3d_array.shape == (21, 3)
        points = keypoint_3d_array[[0, 5, 9], :]
        x_vector = points[0] - points[2]
        pts_centered = points - np.mean(points, axis=0, keepdims=True)
        u, s, v = np.linalg.svd(pts_centered)
        normal = v[2, :]
        x = x_vector - np.sum(x_vector * normal) * normal
        x /= (np.linalg.norm(x) + 1e-8)
        z = np.cross(x, normal)
        if np.sum(z * (points[1] - points[2])) < 0:
            normal *= -1
            z *= -1
        frame = np.stack([x, normal, z], axis=1)
        return frame

    def detect(self, rgb):
        results = self.hand_detector.process(rgb)
        if not results or not results.multi_hand_landmarks:
            return 0, None, None, None, None, None, None

        # 找到目标手
        desired_hand_num = -1
        for i, hand_handedness in enumerate(results.multi_handedness):
            label = hand_handedness.classification[0].label
            if label == self.detected_hand_type:
                desired_hand_num = i
                break
        if desired_hand_num < 0:
            return 0, None, None, None, None, None, None

        keypoint_3d = results.multi_hand_world_landmarks[desired_hand_num]
        keypoint_2d = results.multi_hand_landmarks[desired_hand_num]
        num_box = len(results.multi_hand_landmarks)

        # 转为numpy
        keypoint_3d_raw = self.parse_keypoint_3d(keypoint_3d)
        wrist_world_pos = keypoint_3d_raw[0].copy()

        # wrist-centered
        keypoint_3d_centered = keypoint_3d_raw - wrist_world_pos[None, :]

        # 旋转矩阵
        wrist_rot = self.estimate_frame_from_hand_points(keypoint_3d_centered)
        joint_pos = keypoint_3d_centered @ wrist_rot @ self.operator2mano

        # openness
        openness, distances = compute_hand_openness(joint_pos)

        # 使用手掌宽度比例缩放得到近似真实世界坐标
        joint_pos_world = joint_pos.copy()
        if self.real_palm_width > 0:
            palm_width_pixel = np.linalg.norm(joint_pos[[5, 17], :], axis=1).sum()
            scale = self.real_palm_width / max(palm_width_pixel, 1e-6)
            joint_pos_world *= scale

        return int(num_box), joint_pos, keypoint_2d, wrist_rot, openness, wrist_world_pos, joint_pos_world

    def close(self):
        if self.hand_detector:
            self.hand_detector.close()


# ========== 逆解算常量 ==========
ARM_LENGTH = 0.145  # 连杆长度 (米)
ENCODER_PER_90_DEG = 410  # 410个编码对应90度
ENCODER_PER_DEG = ENCODER_PER_90_DEG / 90.0  # 每度对应的编码数

# 舵机编码配置
SERVO_CONFIG = {
    3: {  # 底部舵机
        'zero_pos': 400,
        'max_pos': 1023,
        'direction': 1,
        'name': '底部'
    },
    2: {  # 中间舵机
        'zero_pos': 500,
        'max_pos': 0,
        'direction': -1,
        'name': '中间'
    },
    1: {  # 顶端舵机
        'zero_pos': 475,
        'max_pos': 70,
        'direction': -1,
        'name': '顶端'
    }
}


class HandFollowMode(BaseMode):
    """
    手部跟随模式
    
    读取数据：
    - position: 手部3D位置 [x, y, z]
    - euler: 手部欧拉角 [roll, pitch, yaw]
    - openness: 手掌张开程度 (0-1)
    
    舵机配置（3个舵机）：
    - 舵机1：底座旋转（yaw）
    - 舵机2：第一关节俯仰（pitch）
    - 舵机3：第二关节俯仰（roll）
    """
    
    MODE_NAME = "手部跟随"
    
    def __init__(self, controller):
        super().__init__(controller)
        
        # 舵机配置（使用逆解算配置）
        self.servo_ids = [1, 2, 3]
        self.servo_limits = {
            3: (400, 1023),   # 底部
            2: (0, 500),      # 中间
            1: (70, 475),     # 顶端
        }
        self.current_positions = {1: 475, 2: 500, 3: 400}
        
        # 手部检测相关
        self._hand_detector = None
        self._kalman_filter = None
        self._camera_matrix = None
        self._use_single_hand_detector = False
        
        # 用于 PnP 求解的关键点索引
        # 0: WRIST, 5: INDEX_MCP, 9: MIDDLE_MCP, 13: RING_MCP, 17: PINKY_MCP
        self._keypoint_indices = [0, 5, 9, 13, 17]
        
        # 最新的手部数据
        self._hand_data: Optional[Dict[str, Any]] = None
        self._no_hand_count = 0
        self._no_hand_threshold = 30
        
        # 距离历史（用于异常检测）
        self._distance_history = []
        self._max_history = 30
        
        # 舵机发送频率控制
        self._servo_send_interval = 0.1  # 10Hz，可调整
        self._last_servo_send_time = 0
        
        # 握拳暂停功能
        self._paused = False  # 是否处于暂停状态
        self._pause_threshold = 0.7   # openness < 此值时暂停
        self._resume_threshold = 0.9  # openness > 此值时恢复
        
        # 比1手势退出功能
        self._pointing_one_start_time = None  # 比1手势开始时间
        self._pointing_one_exit_seconds = 3.0  # 比1手势持续多少秒后退出
        
    def on_enter(self):
        """进入模式：初始化检测器"""
        self._init_hand_detector()
        self._init_kalman_filter()
        self._move_to_home()
        self._print("等待检测手部...")
        self._print("读取数据: position, euler, openness")
        
    def on_exit(self):
        """退出模式：释放资源"""
        if self._hand_detector:
            self._hand_detector.close()
            self._hand_detector = None
        self._move_to_home()
        
    def _init_hand_detector(self):
        """初始化手部检测器"""
        try:
            # 使用内嵌的 SingleHandDetector
            self._hand_detector = EmbeddedSingleHandDetector(
                hand_type="Right",
                min_detection_confidence=0.8,
                min_tracking_confidence=0.8,
                use_pose=False,
                real_palm_width=0.085
            )
            self._use_single_hand_detector = True
            self._print("使用 EmbeddedSingleHandDetector")
            
        except ImportError as e:
            self._print(f"手部检测器初始化失败: {e}")
            self._hand_detector = None
            
    def _init_kalman_filter(self):
        """初始化卡尔曼滤波器（简化版，不依赖外部模块）"""
        # 使用简单的指数平滑代替卡尔曼滤波
        self._kalman_filter = None
        self._smooth_alpha = 0.3  # 平滑系数
        self._smooth_state = None
        self._print("使用简单平滑滤波")
            
    def _calibrate_camera(self, frame_shape):
        """简单的相机标定"""
        if self._camera_matrix is None:
            h, w = frame_shape[:2]
            fx = fy = w * 1.2
            cx, cy = w / 2, h / 2
            self._camera_matrix = np.array([
                [fx, 0, cx],
                [0, fy, cy],
                [0, 0, 1]
            ], dtype=np.float32)
            self._dist_coeffs = np.zeros(5)
            
    def _move_to_home(self):
        """移动到初始位置（直立中位）"""
        # 直立中位: b=0.1, theta_0=90, beta=0
        home_positions = {3: 598, 2: 77, 1: 276}
        self._move_servos(home_positions, speed=250)
        self.current_positions = home_positions.copy()
        
    def update(self, frame=None, voice_text: str = None) -> bool:
        """更新模式"""
        if frame is None:
            return True
            
        # 相机标定
        self._calibrate_camera(frame.shape)
        
        # 检测手部，获取 position, euler, openness
        hand_data = self._detect_hand(frame)
        
        if hand_data:
            self._no_hand_count = 0
            self._hand_data = hand_data
            
            # 打印手部数据
            pos = hand_data['position']
            euler = hand_data['euler']
            openness = hand_data['openness']
            ik_input = hand_data['ik_input']
            
            # 原始数据
            self._debug(f"Pos: [{pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}] | "
                       f"Euler: [{euler[0]:.1f}, {euler[1]:.1f}, {euler[2]:.1f}] | "
                       f"Open: {openness:.2f}")
            
            # === 获取关节位置用于手势检测 ===
            joint_pos = hand_data.get('joint_pos')
            
            # === 比1手势检测（退出功能） ===
            import time
            is_pointing_one = detect_pointing_one(joint_pos) if joint_pos is not None else False
            
            if is_pointing_one:
                if self._pointing_one_start_time is None:
                    # 开始计时
                    self._pointing_one_start_time = time.time()
                    self._paused = True  # 比1也会暂停
                    self._print("☝️ 检测到比1手势，暂停中...")
                else:
                    # 检查是否超过退出时间
                    elapsed = time.time() - self._pointing_one_start_time
                    remaining = self._pointing_one_exit_seconds - elapsed
                    if remaining > 0:
                        self._debug(f"[比1手势] 保持 {elapsed:.1f}s，还需 {remaining:.1f}s 退出")
                    else:
                        self._print(f"☝️ 比1手势保持 {self._pointing_one_exit_seconds}s，退出模式")
                        return False  # 返回 False 退出模式
            else:
                # 不是比1手势，重置计时
                if self._pointing_one_start_time is not None:
                    self._pointing_one_start_time = None
                    self._print("☝️ 比1手势取消")
                
                # === 握拳暂停功能 ===
                if not self._paused and openness < self._pause_threshold:
                    # 进入暂停状态
                    self._paused = True
                    self._print(f"✋ 握拳暂停 (openness={openness:.2f})")
                elif self._paused and openness > self._resume_threshold:
                    # 恢复跟随
                    self._paused = False
                    self._print(f"👋 恢复跟随 (openness={openness:.2f})")
            
            # 暂停时不移动舵机
            if self._paused:
                self._debug(f"[暂停中] openness={openness:.2f}, 需要>{self._resume_threshold:.1f}恢复")
                return True
            
            # 逆解输入数组: [pitch, middle_mcp_y, distance]
            self._debug(f"IK Input: [pitch={ik_input[0]:.1f}°, mcp_y={ik_input[1]:.3f}, dist={ik_input[2]:.3f}m]")
            
            # 根据手部数据计算舵机位置
            servo_positions = self._calculate_servo_positions(hand_data)
            
            # 移动舵机
            self._move_servos(servo_positions)
        else:
            self._no_hand_count += 1
            if self._no_hand_count == self._no_hand_threshold:
                self._print("未检测到手部，等待中...")
            
            # 预测（如果有卡尔曼滤波器）
            if self._kalman_filter:
                self._kalman_filter.predict()
                
        return True
        
    def _detect_hand(self, frame) -> Optional[Dict[str, Any]]:
        """
        检测手部，返回 position, euler, openness
        
        Returns:
            {
                'position': [x, y, z],      # 3D位置（米）
                'euler': [roll, pitch, yaw], # 欧拉角（度）
                'openness': float,           # 张开程度 0-1
                'raw': {...}                 # 原始数据
            }
        """
        if self._hand_detector is None:
            return None
            
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        return self._detect_with_single_hand_detector(rgb, frame.shape)
            
    def _detect_with_single_hand_detector(self, rgb, frame_shape) -> Optional[Dict]:
        """使用 EmbeddedSingleHandDetector 检测"""
        num_box, joint_pos, keypoint_2d, wrist_rot, openness, wrist_world_pos, joint_pos_world = \
            self._hand_detector.detect(rgb)
            
        if num_box == 0 or joint_pos is None:
            return None
            
        h, w = frame_shape[:2]
        
        # 准备 2D 关键点
        keypoints_2d = np.array([
            [lm.x * w, lm.y * h] for lm in keypoint_2d.landmark
        ], dtype=np.float32)
        
        # 中指根部关节（MIDDLE_MCP, index=9）在图像中的竖直位置（归一化 0-1）
        middle_mcp_y = keypoint_2d.landmark[9].y  # 归一化坐标
        
        # 用于 PnP 求解的点
        X_local = joint_pos[self._keypoint_indices]
        x_2d = keypoints_2d[self._keypoint_indices]
        
        # PnP 求解获取 3D 位置
        success, rvec, tvec = self._solve_pnp(X_local, x_2d)
        
        if not success:
            return None
            
        t_raw = tvec.flatten()
        distance = np.linalg.norm(t_raw)
        
        # 距离异常检测
        t_raw = self._filter_distance(t_raw, distance)
        
        # 从旋转矩阵提取欧拉角（不依赖 scipy）
        euler_rad = self._rotation_matrix_to_euler(wrist_rot)
        
        # 简单平滑滤波
        position = t_raw
        euler_deg = np.degrees(euler_rad)
        openness_filtered = openness if openness is not None else 0.5
        
        if self._smooth_state is not None:
            alpha = self._smooth_alpha
            position = alpha * t_raw + (1 - alpha) * self._smooth_state[:3]
            euler_deg = alpha * euler_deg + (1 - alpha) * self._smooth_state[3:6]
            openness_filtered = alpha * openness_filtered + (1 - alpha) * self._smooth_state[6]
        
        self._smooth_state = np.array([
            position[0], position[1], position[2],
            euler_deg[0], euler_deg[1], euler_deg[2],
            openness_filtered
        ])
        
        # Clip position[2] (距离) 到 0.25-0.7 米
        position = np.array(position)
        position[2] = np.clip(position[2], 0.25, 0.7)
        
        # Clip euler[1] (pitch) 到 ±30 度
        euler_deg = np.array(euler_deg)
        euler_deg[1] = np.clip(euler_deg[1], -30, 30)
        
        # 逆解输入数组: [euler[1](俯仰角), middle_mcp_y(中指根部竖直位置), distance(距离)]
        ik_input = [
            float(np.clip((euler_deg[2]-90), -30, 60)),                      # 俯仰角 (度) 利用手的yaw
            float(np.clip(middle_mcp_y, 0.1, 0.8)),   # 中指根部 y 坐标 (clip 到 0.1-0.8)
            float(position[2])                        # 距离 (米)
        ]
            
        return {
            'position': position.tolist(),
            'euler': euler_deg.tolist(),
            'openness': float(openness_filtered),
            'middle_mcp_y': float(middle_mcp_y),
            'ik_input': ik_input,
            'joint_pos': joint_pos,  # 添加关节位置用于手势检测
            'raw': {
                'tvec': t_raw.tolist(),
                'euler_rad': euler_rad.tolist(),
                'distance': distance,
            }
        }
    
    def _rotation_matrix_to_euler(self, R):
        """从旋转矩阵提取欧拉角 (XYZ顺序)"""
        sy = math.sqrt(R[0, 0] ** 2 + R[1, 0] ** 2)
        singular = sy < 1e-6
        
        if not singular:
            x = math.atan2(R[2, 1], R[2, 2])
            y = math.atan2(-R[2, 0], sy)
            z = math.atan2(R[1, 0], R[0, 0])
        else:
            x = math.atan2(-R[1, 2], R[1, 1])
            y = math.atan2(-R[2, 0], sy)
            z = 0
        
        return np.array([x, y, z])
        
    def _solve_pnp(self, object_points, image_points) -> Tuple[bool, Any, Any]:
        """PnP 求解"""
        methods = [
            cv2.SOLVEPNP_EPNP,
            cv2.SOLVEPNP_ITERATIVE,
            cv2.SOLVEPNP_SQPNP,
        ]
        
        for method in methods:
            try:
                success, rvec, tvec = cv2.solvePnP(
                    object_points, image_points,
                    self._camera_matrix, self._dist_coeffs,
                    flags=method
                )
                
                if success:
                    # 验证结果
                    distance = np.linalg.norm(tvec)
                    if 0.2 < distance < 1.5:  # 合理距离范围
                        return True, rvec, tvec
                        
            except cv2.error:
                continue
                
        return False, None, None
        
    def _filter_distance(self, t_raw, distance):
        """距离异常过滤"""
        self._distance_history.append(distance)
        if len(self._distance_history) > self._max_history:
            self._distance_history.pop(0)
            
        if len(self._distance_history) > 5:
            avg = np.mean(self._distance_history)
            std = np.std(self._distance_history)
            z_score = abs(distance - avg) / (std + 1e-6)
            
            if z_score > 2.0:
                t_raw = t_raw.copy()
                t_raw[2] = avg
                
        return t_raw
        
    def _calculate_servo_positions(self, hand_data: Dict) -> Dict[int, int]:
        """
        根据手部数据计算舵机位置（使用逆解算）
        
        映射关系:
        - ik_input[0] = pitch = beta (灯俯仰)
        - ik_input[1] = middle_mcp_y: 0.8~0.1 → y: 0.1~0.28
        - ik_input[2] = distance: 0.7~0.25 → x: -0.22~0
        - theta_0 = atan2(y, x)
        - b = sqrt(x² + y²), 约束到 <= 0.28
        """
        ik_input = hand_data.get('ik_input')
        if ik_input is None:
            return self.current_positions
        
        beta_deg = ik_input[0]    # pitch → beta
        mcp_y = ik_input[1]       # 0.1~0.8
        dist = ik_input[2]        # 0.25~0.7
        
        # === 映射到 x, y ===
        # x: dist 0.7→-0.22, dist 0.25→0
        x = -0.22 * (dist - 0.25) / (0.7 - 0.25)
        
        # y: mcp_y 0.8→0.1, mcp_y 0.1→0.28
        y = 0.1 + (0.28 - 0.1) * (0.8 - mcp_y) / (0.8 - 0.1)
        
        # === 从 x, y 计算 b 和 theta_0 ===
        b = math.sqrt(x**2 + y**2)
        
        # 检查是否在圆外，如果 b > 0.28 则约束到 0.28
        if b > 0.28:
            b = 0.28
        
        # theta_0 = atan2(y, x)，转换为度
        if abs(x) < 1e-6:
            theta_0_deg = 90.0 if y > 0 else -90.0
        else:
            theta_0_deg = math.degrees(math.atan2(y, x))
        
        # === 逆解算 ===
        alpha_1, alpha_2, alpha_3, valid = self._inverse_kinematics(b, theta_0_deg, beta_deg)
        
        if not valid:
            self._debug(f"IK 无效: b={b:.3f}, theta_0={theta_0_deg:.1f}, beta={beta_deg:.1f}")
            return self.current_positions
        
        # === 角度转编码 ===
        enc_3 = self._angle_to_encoder(3, alpha_1)  # 底部
        enc_2 = self._angle_to_encoder(2, alpha_2)  # 中间
        enc_1 = self._angle_to_encoder(1, alpha_3)  # 顶端
        
        self._debug(f"IK: x={x:.3f}, y={y:.3f} → b={b:.3f}, θ₀={theta_0_deg:.1f}°, β={beta_deg:.1f}°")
        self._debug(f"    α₁={alpha_1:.1f}°, α₂={alpha_2:.1f}°, α₃={alpha_3:.1f}° → enc=[{enc_3}, {enc_2}, {enc_1}]")
        
        return {
            3: enc_3,  # 底部
            2: enc_2,  # 中间
            1: enc_1,  # 顶端
        }
    
    def _inverse_kinematics(self, b, theta_0_deg, beta_deg=0):
        """
        台灯连杆逆解算
        
        Args:
            b: 等腰三角形底边长 (米)
            theta_0_deg: 底边角度 (度)
            beta_deg: 灯俯仰角度 (度)
        
        Returns:
            (alpha_1, alpha_2, alpha_3, valid): 三个舵机角度, 是否有效
        """
        a = ARM_LENGTH
        
        # 检查三角形是否有效
        if b >= 2 * a or b <= 0:
            return None, None, None, False
        
        # sin(theta_1) = b/(2a)
        sin_theta_1 = b / (2 * a)
        if abs(sin_theta_1) > 1:
            return None, None, None, False
        
        theta_1_rad = math.asin(sin_theta_1)
        theta_1_deg = math.degrees(theta_1_rad)
        
        # cos(theta_2) = b/(2a)
        cos_theta_2 = b / (2 * a)
        if abs(cos_theta_2) > 1:
            return None, None, None, False
        
        theta_2_rad = math.acos(cos_theta_2)
        theta_2_deg = math.degrees(theta_2_rad)
        
        # 计算舵机角度
        alpha_1 = theta_0_deg - theta_2_deg  # 底部
        alpha_2 = 180 - 2 * theta_1_deg      # 中间
        alpha_3 = 180 + beta_deg - alpha_2 - alpha_1  # 顶端
        
        # 检查角度是否在舵机可达范围内
        # ID3 (底部): 0° ~ 136° (400→1023, 623编码 / 4.56 ≈ 136°)
        # ID2 (中间): 0° ~ 109° (500→0, 500编码 / 4.56 ≈ 109°)
        # ID1 (顶端): 0° ~ 88°  (475→70, 405编码 / 4.56 ≈ 88°)
        if not (0 <= alpha_1 <= 136):
            return None, None, None, False
        if not (0 <= alpha_2 <= 109):
            return None, None, None, False
        if not (0 <= alpha_3 <= 88):
            return None, None, None, False
        
        return alpha_1, alpha_2, alpha_3, True
    
    def _angle_to_encoder(self, servo_id, angle_deg):
        """角度转换为编码值"""
        config = SERVO_CONFIG[servo_id]
        
        encoder_offset = angle_deg * ENCODER_PER_DEG * config['direction']
        encoder = int(config['zero_pos'] + encoder_offset)
        
        # 限幅
        if config['direction'] > 0:
            encoder = max(config['zero_pos'], min(config['max_pos'], encoder))
        else:
            encoder = max(config['max_pos'], min(config['zero_pos'], encoder))
        
        return encoder
        
    def _move_servos(self, positions: Dict[int, int], speed: int = None):
        """移动舵机（带频率控制）"""
        import time
        now = time.time()
        
        # 频率控制：时间没到就跳过
        if now - self._last_servo_send_time < self._servo_send_interval:
            return
        self._last_servo_send_time = now
        
        if self.controller:
            servo_thread = getattr(self.controller, '_servo_thread', None)
            if servo_thread:
                for servo_id, pos in positions.items():
                    # 限幅
                    min_pos, max_pos = self.servo_limits.get(servo_id, (0, 1023))
                    pos = max(min_pos, min(max_pos, pos))
                    servo_thread.move(servo_id, pos, speed if speed else 500)
                    self.current_positions[servo_id] = pos
            else:
                # 模拟模式
                self._debug(f"[MockServo] 移动: {positions}")
                
    def handle_voice(self, text: str) -> bool:
        """处理语音命令"""
        return False
        
    def get_hand_data(self) -> Optional[Dict[str, Any]]:
        """获取最新的手部数据（供外部使用）"""
        return self._hand_data


# ==================== 独立测试 ====================

# 舵机控制配置
SERIAL_PORT = '/dev/ttyUSB0'
BAUDRATE = 1000000


class RealServoController:
    """真正的舵机控制器（用于独立测试）"""
    
    # 寄存器地址
    STS_GOAL_POSITION_L = 42
    
    def __init__(self, port=SERIAL_PORT, baudrate=BAUDRATE):
        self.port = port
        self.baudrate = baudrate
        self.port_handler = None
        self.packet_handler = None
        self._connected = False
        self._speed = 500  # 默认速度
        
    def connect(self) -> bool:
        """连接舵机"""
        try:
            import sys
            import os
            # 添加 scservo_sdk 路径
            sdk_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', 'FTServo_Python')
            sys.path.insert(0, os.path.abspath(sdk_path))
            
            from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS
            
            self.COMM_SUCCESS = COMM_SUCCESS
            
            # 打开串口
            self.port_handler = PortHandler(self.port)
            if not self.port_handler.openPort():
                print(f"✗ 无法打开串口: {self.port}")
                return False
            
            if not self.port_handler.setBaudRate(self.baudrate):
                print(f"✗ 无法设置波特率: {self.baudrate}")
                return False
            
            # 使用 sms_sts 协议处理器
            self.packet_handler = sms_sts(self.port_handler)
            
            self._connected = True
            print(f"✓ 舵机连接成功: {self.port} @ {self.baudrate}")
            return True
            
        except ImportError as e:
            print(f"✗ scservo_sdk 导入失败: {e}")
            return False
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.port_handler:
            self.port_handler.closePort()
            self._connected = False
            print("舵机断开连接")
    
    def write_position(self, servo_id: int, position: int, speed: int = None):
        """写入单个舵机位置和速度（大端序，和 my_servo_control.py 一致）"""
        if not self._connected:
            return
        
        position = max(0, min(1023, position))
        speed = speed if speed is not None else self._speed
        
        # 数据包: 位置高, 位置低, 时间高, 时间低, 速度高, 速度低
        data = [
            (position >> 8) & 0xFF,  # 位置高字节
            position & 0xFF,         # 位置低字节
            0, 0,                    # 时间（不使用）
            (speed >> 8) & 0xFF,     # 速度高字节
            speed & 0xFF             # 速度低字节
        ]
        
        try:
            self.packet_handler.writeTxRx(servo_id, self.STS_GOAL_POSITION_L, len(data), data)
        except Exception as e:
            print(f"写入舵机 {servo_id} 失败: {e}")
    
    def sync_move(self, positions: Dict[int, int], speed: int = None):
        """逐个写入舵机位置（非同步广播，逐个发送）"""
        if not self._connected:
            return
        
        for servo_id, pos in positions.items():
            self.write_position(servo_id, pos, speed)


class ServoThread:
    """
    舵机发送线程（独立线程，避免阻塞主线程）
    
    主线程调用 set_position() 只是把指令塞进队列，立即返回。
    独立线程循环从队列取指令，调用 writeTxRx 发送。
    """
    
    def __init__(self, servo_controller: RealServoController):
        import threading
        import queue
        
        self._controller = servo_controller
        self._speed = 500  # 默认速度
        
        # 指令队列（最多缓存10个，满了就丢弃旧的）
        self._queue = queue.Queue(maxsize=10)
        
        # 发送线程
        self._running = True
        self._thread = threading.Thread(target=self._send_loop, daemon=True, name="ServoSendThread")
        self._thread.start()
        print("✓ 舵机发送线程已启动")
    
    def set_position(self, servo_id: int, position: int, speed: int = None):
        """
        设置舵机位置（非阻塞，塞进队列立即返回）
        """
        import queue
        spd = speed if speed is not None else self._speed
        try:
            # put_nowait: 队列满就抛异常，不阻塞
            self._queue.put_nowait((servo_id, position, spd))
        except queue.Full:
            # 队列满了，丢弃这条指令（保证实时性）
            pass
    
    def _send_loop(self):
        """发送线程主循环：不断从队列取指令发送"""
        while self._running:
            try:
                # 等待指令，超时0.1秒检查一次 _running
                servo_id, position, speed = self._queue.get(timeout=0.1)
                self._controller.write_position(servo_id, position, speed)
            except:
                # queue.Empty 或其他异常，继续循环
                pass
    
    def stop(self):
        """停止发送线程"""
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout=1)
        print("舵机发送线程已停止")


def test_hand_follow_mode():
    """独立测试手部跟随模式（真实舵机控制）"""
    print("=" * 50)
    print("手部跟随模式 - 独立测试 (真实舵机)")
    print("=" * 50)
    print("读取数据: position, euler, openness")
    print(f"串口: {SERIAL_PORT}")
    print("按 'q' 退出测试")
    print()
    
    # 创建真实舵机控制器
    servo_controller = RealServoController(SERIAL_PORT, BAUDRATE)
    
    class TestController:
        def __init__(self):
            self.debug = True
            self._servo_thread = None
    
    controller = TestController()
    
    # 尝试连接舵机
    if servo_controller.connect():
        controller._servo_thread = ServoThread(servo_controller)
        print("✓ 使用真实舵机控制")
    else:
        print("⚠ 舵机连接失败，使用模拟模式")
    
    mode = HandFollowMode(controller)
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("错误: 无法打开摄像头")
        return
        
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    mode.enter()
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
                
            mode.update(frame=frame)
            
            # 显示手部数据
            hand_data = mode.get_hand_data()
            if hand_data:
                pos = hand_data['position']
                euler = hand_data['euler']
                openness = hand_data['openness']
                ik_input = hand_data['ik_input']
                
                y = 30
                cv2.putText(frame, f"Pos: [{pos[0]:.2f}, {pos[1]:.2f}, {pos[2]:.2f}]",
                           (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                y += 30
                cv2.putText(frame, f"Euler: [{euler[0]:.1f}, {euler[1]:.1f}, {euler[2]:.1f}]",
                           (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                y += 30
                cv2.putText(frame, f"Openness: {openness:.2f}",
                           (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                y += 30
                # 逆解输入数组: [pitch, middle_mcp_y, distance]
                cv2.putText(frame, f"IK Input: [{ik_input[0]:.1f}, {ik_input[1]:.3f}, {ik_input[2]:.3f}]",
                           (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
            else:
                cv2.putText(frame, "No hand detected", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                           
            cv2.putText(frame, "Press 'q' to quit", (10, frame.shape[0] - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                       
            cv2.imshow("Hand Follow Mode Test", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        mode.exit()
        cap.release()
        cv2.destroyAllWindows()
        
        # 停止舵机发送线程
        if controller._servo_thread:
            controller._servo_thread.stop()
        
        # 断开舵机连接
        if servo_controller._connected:
            servo_controller.disconnect()
        
        print("测试结束")


if __name__ == "__main__":
    test_hand_follow_mode()
