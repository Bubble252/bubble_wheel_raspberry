#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
台灯逆运动学模块
提供 b, theta_0, beta 到舵机编码的转换

坐标系说明:
- b: 等腰三角形底边长 (米), 范围 0 ~ 0.28
- theta_0: 底边角度 (度), 即台灯朝向, 范围约 0 ~ 180
- beta: 灯头俯仰角 (度), 范围约 -30 ~ 60

舵机配置:
- 舵机1 (顶端): 控制灯头俯仰
- 舵机2 (中间): 控制中间关节
- 舵机3 (底部): 控制底座旋转
"""

import math
from typing import Dict, Tuple, Optional

# ========== 常量 ==========
ARM_LENGTH = 0.145  # 连杆长度 (米)
ENCODER_PER_90_DEG = 410  # 410个编码对应90度
ENCODER_PER_DEG = ENCODER_PER_90_DEG / 90.0  # 每度对应的编码数 ≈ 4.56

# 舵机编码配置
SERVO_CONFIG = {
    3: {  # 底部舵机 (ID3)
        'zero_pos': 400,      # 零位编码
        'max_pos': 1023,      # 最大编码
        'direction': 1,       # 方向 (正向)
        'name': '底部',
        'angle_range': (0, 136),  # 角度范围
    },
    2: {  # 中间舵机 (ID2)
        'zero_pos': 500,      # 零位编码
        'max_pos': 0,         # 最大编码 (反向)
        'direction': -1,      # 方向 (反向)
        'name': '中间',
        'angle_range': (0, 109),
    },
    1: {  # 顶端舵机 (ID1)
        'zero_pos': 475,      # 零位编码
        'max_pos': 70,        # 最大编码 (反向)
        'direction': -1,      # 方向 (反向)
        'name': '顶端',
        'angle_range': (0, 88),
    }
}

# 舵机限位
SERVO_LIMITS = {
    3: (400, 1023),   # 底部
    2: (0, 500),      # 中间
    1: (70, 475),     # 顶端
}

# 默认姿态 (约45度前倾)
DEFAULT_POSE = {
    'b': 0.20,
    'theta_0': 90.0,
    'beta': 0.0,
}

# 默认姿态对应的编码 (通过逆解算计算: b=0.2, theta_0=90, beta=0)
HOME_POSITIONS = {3: 598, 2: 77, 1: 276}


def inverse_kinematics(b: float, theta_0: float, beta: float = 0.0) -> Tuple[Optional[float], Optional[float], Optional[float], bool]:
    """
    台灯连杆逆解算
    
    Args:
        b: 等腰三角形底边长 (米), 0 < b < 2*ARM_LENGTH
        theta_0: 底边角度 (度), 台灯朝向
        beta: 灯头俯仰角度 (度)
    
    Returns:
        (alpha_1, alpha_2, alpha_3, valid): 三个舵机角度(度), 是否有效
        - alpha_1: 底部舵机角度 (ID3)
        - alpha_2: 中间舵机角度 (ID2)
        - alpha_3: 顶端舵机角度 (ID1)
    """
    a = ARM_LENGTH
    
    # 检查 b 是否有效
    if b <= 0 or b >= 2 * a:
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
    alpha_1 = theta_0 - theta_2_deg      # 底部 (ID3)
    alpha_2 = 180 - 2 * theta_1_deg      # 中间 (ID2)
    alpha_3 = 180 + beta - alpha_2 - alpha_1  # 顶端 (ID1)
    
    # 检查角度是否在舵机可达范围内
    config_3 = SERVO_CONFIG[3]
    config_2 = SERVO_CONFIG[2]
    config_1 = SERVO_CONFIG[1]
    
    if not (config_3['angle_range'][0] <= alpha_1 <= config_3['angle_range'][1]):
        return None, None, None, False
    if not (config_2['angle_range'][0] <= alpha_2 <= config_2['angle_range'][1]):
        return None, None, None, False
    if not (config_1['angle_range'][0] <= alpha_3 <= config_1['angle_range'][1]):
        return None, None, None, False
    
    return alpha_1, alpha_2, alpha_3, True


def angle_to_encoder(servo_id: int, angle_deg: float) -> int:
    """
    角度转换为编码值
    
    Args:
        servo_id: 舵机ID (1, 2, 3)
        angle_deg: 角度 (度)
    
    Returns:
        编码值 (0-1023)
    """
    config = SERVO_CONFIG[servo_id]
    
    encoder_offset = angle_deg * ENCODER_PER_DEG * config['direction']
    encoder = int(config['zero_pos'] + encoder_offset)
    
    # 限幅
    min_pos, max_pos = SERVO_LIMITS[servo_id]
    encoder = max(min_pos, min(max_pos, encoder))
    
    return encoder


def encoder_to_angle(servo_id: int, encoder: int) -> float:
    """
    编码值转换为角度
    
    Args:
        servo_id: 舵机ID (1, 2, 3)
        encoder: 编码值 (0-1023)
    
    Returns:
        角度 (度)
    """
    config = SERVO_CONFIG[servo_id]
    
    encoder_offset = encoder - config['zero_pos']
    angle_deg = encoder_offset / (ENCODER_PER_DEG * config['direction'])
    
    return angle_deg


def pose_to_encoders(b: float, theta_0: float, beta: float = 0.0) -> Tuple[Dict[int, int], bool]:
    """
    姿态参数转换为舵机编码
    
    Args:
        b: 等腰三角形底边长 (米)
        theta_0: 底边角度 (度)
        beta: 灯头俯仰角度 (度)
    
    Returns:
        ({舵机ID: 编码}, 是否有效)
    """
    alpha_1, alpha_2, alpha_3, valid = inverse_kinematics(b, theta_0, beta)
    
    if not valid:
        return {}, False
    
    encoders = {
        3: angle_to_encoder(3, alpha_1),  # 底部
        2: angle_to_encoder(2, alpha_2),  # 中间
        1: angle_to_encoder(1, alpha_3),  # 顶端
    }
    
    return encoders, True


def interpolate_pose(pose1: Dict, pose2: Dict, t: float) -> Dict:
    """
    在两个姿态之间插值
    
    Args:
        pose1: 起始姿态 {b, theta_0, beta}
        pose2: 结束姿态 {b, theta_0, beta}
        t: 插值参数 0-1
    
    Returns:
        插值后的姿态
    """
    t = max(0.0, min(1.0, t))
    
    return {
        'b': pose1['b'] + (pose2['b'] - pose1['b']) * t,
        'theta_0': pose1['theta_0'] + (pose2['theta_0'] - pose1['theta_0']) * t,
        'beta': pose1['beta'] + (pose2['beta'] - pose1['beta']) * t,
    }


def get_home_pose() -> Dict:
    """获取默认姿态"""
    return DEFAULT_POSE.copy()


def get_home_encoders() -> Dict[int, int]:
    """获取默认姿态的编码"""
    return HOME_POSITIONS.copy()


# ========== 测试函数 ==========
def test_kinematics():
    """测试逆解算"""
    print("=" * 50)
    print("逆运动学测试")
    print("=" * 50)
    print(f"连杆长度: {ARM_LENGTH}m")
    print(f"有效 b 范围: 约 0.17m ~ 0.28m")
    print()
    
    test_cases = [
        # (b, theta_0, beta, 描述)
        (0.17, 90, 0, "接近竖直"),
        (0.20, 90, 0, "默认姿态(约45°前倾)"),
        (0.24, 90, 0, "较大前倾"),
        (0.27, 90, 0, "接近极限前倾"),
        (0.20, 60, 0, "向左旋转"),
        (0.20, 120, 0, "向右旋转"),
        (0.18, 90, 25, "抬头"),
        (0.23, 90, -15, "低头"),
        (0.22, 70, 15, "组合姿态1"),
        (0.24, 110, -10, "组合姿态2"),
    ]
    
    for b, theta_0, beta, desc in test_cases:
        encoders, valid = pose_to_encoders(b, theta_0, beta)
        
        if valid:
            print(f"\n{desc}:")
            print(f"  输入: b={b:.3f}m, θ₀={theta_0}°, β={beta}°")
            print(f"  编码: ID3={encoders[3]}, ID2={encoders[2]}, ID1={encoders[1]}")
            
            # 反算角度
            alpha_1, alpha_2, alpha_3, _ = inverse_kinematics(b, theta_0, beta)
            print(f"  角度: α₁={alpha_1:.1f}°, α₂={alpha_2:.1f}°, α₃={alpha_3:.1f}°")
        else:
            print(f"\n{desc}: ✗ 无效 (b={b}, θ₀={theta_0}, β={beta})")
    
    print("\n" + "=" * 50)


if __name__ == "__main__":
    test_kinematics()
