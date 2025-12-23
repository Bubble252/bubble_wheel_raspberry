#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
台灯连杆逆解算验证脚本

连杆配置:
- ID3 (底部): 0度=400, 最大=1023 (正方向)
- ID2 (中间): 0度=500, 最大=0 (反方向)
- ID1 (顶端): 0度=475, 最大=70 (反方向), 固定为475

逆解算法:
- 前两个杆构成等腰三角形, 腰长 a = 0.145m
- 输入: 底边长 b, 底边角度 theta_0
- 输出: alpha_1 (底部), alpha_2 (中间)
"""

import argparse
import math
import time
import sys

# 尝试导入舵机库（可选）
try:
    from scservo_sdk import *
    SERVO_SDK_AVAILABLE = True
except ImportError:
    SERVO_SDK_AVAILABLE = False
    print("⚠ scservo_sdk 未找到，仅支持模拟模式")

# ========== 机械参数 ==========
ARM_LENGTH = 0.145  # 连杆长度 (米)

# 舵机编码配置
SERVO_CONFIG = {
    3: {  # 底部舵机
        'zero_pos': 400,      # 0度位置编码
        'max_pos': 1023,      # 最大位置编码
        'direction': 1,       # 正方向
        'name': '底部'
    },
    2: {  # 中间舵机
        'zero_pos': 500,      # 0度位置编码
        'max_pos': 0,         # 最大位置编码
        'direction': -1,      # 反方向
        'name': '中间'
    },
    1: {  # 顶端舵机
        'zero_pos': 475,      # 0度位置编码
        'max_pos': 70,        # 最小位置编码
        'direction': -1,      # 反方向
        'name': '顶端'
    }
}

# 编码-角度转换
ENCODER_PER_90_DEG = 410  # 410个编码对应90度
ENCODER_PER_DEG = ENCODER_PER_90_DEG / 90.0  # 每度对应的编码数

# 串口配置
DEVICE_PORT = '/dev/ttyUSB0'  # Linux 串口，Windows 改为 'COM5' 等
BAUDRATE = 1000000
STS_GOAL_POSITION_L = 42
STS_PRESENT_POSITION_L = 56

# ========== 逆解算函数 ==========
def inverse_kinematics(b, theta_0_deg, beta_deg=0):
    """
    计算逆解
    
    Args:
        b: 等腰三角形底边长 (米)
        theta_0_deg: 底边角度 (度)
        beta_deg: 灯俯仰角度 (度)，正值向下俯，负值向上仰
    
    Returns:
        (alpha_1, alpha_2, alpha_3, valid): 三个舵机角度(度), 是否有效
    """
    a = ARM_LENGTH
    
    # 检查三角形是否有效
    if b >= 2 * a:
        print(f"  ✗ 无效: b={b:.3f}m 大于等于 2a={2*a:.3f}m")
        return None, None, None, False
    
    if b <= 0:
        print(f"  ✗ 无效: b={b:.3f}m 必须大于0")
        return None, None, None, False
    
    # 计算 theta_1 (顶角的一半, 2*theta_1 是等腰三角形的顶角)
    # sin(theta_1) = b/(2a)
    sin_theta_1 = b / (2 * a)
    if abs(sin_theta_1) > 1:
        print(f"  ✗ 无效: sin(theta_1)={sin_theta_1:.3f} 超出范围")
        return None, None, None, False
    
    theta_1_rad = math.asin(sin_theta_1)
    theta_1_deg = math.degrees(theta_1_rad)
    
    # 计算 theta_2 (等腰三角形的底角)
    # cos(theta_2) = b/(2a)
    # 注意: theta_1 + theta_2 = 90° (因为 sin(theta_1) = cos(theta_2))
    cos_theta_2 = b / (2 * a)
    if abs(cos_theta_2) > 1:
        print(f"  ✗ 无效: cos(theta_2)={cos_theta_2:.3f} 超出范围")
        return None, None, None, False
    
    theta_2_rad = math.acos(cos_theta_2)
    theta_2_deg = math.degrees(theta_2_rad)
    
    # 计算舵机角度
    alpha_1 = theta_0_deg - theta_2_deg  # 底部舵机
    alpha_2 = 180 - 2 * theta_1_deg      # 中间舵机
    alpha_3 = 180 + beta_deg - alpha_2 - alpha_1  # 顶端舵机（灯俯仰）
    
    return alpha_1, alpha_2, alpha_3, True


def angle_to_encoder(servo_id, angle_deg):
    """
    角度转换为编码值
    
    Args:
        servo_id: 舵机ID
        angle_deg: 角度 (度)
    
    Returns:
        编码值
    """
    config = SERVO_CONFIG[servo_id]
    
    # 角度转编码偏移量
    encoder_offset = angle_deg * ENCODER_PER_DEG * config['direction']
    
    # 计算最终编码值
    encoder = int(config['zero_pos'] + encoder_offset)
    
    # 限幅
    if config['direction'] > 0:
        encoder = max(config['zero_pos'], min(config['max_pos'], encoder))
    else:
        encoder = max(config['max_pos'], min(config['zero_pos'], encoder))
    
    return encoder


def encoder_to_angle(servo_id, encoder):
    """
    编码值转换为角度
    
    Args:
        servo_id: 舵机ID
        encoder: 编码值
    
    Returns:
        角度 (度)
    """
    config = SERVO_CONFIG[servo_id]
    encoder_offset = encoder - config['zero_pos']
    angle_deg = encoder_offset / ENCODER_PER_DEG / config['direction']
    return angle_deg


def print_solution(b, theta_0_deg, beta_deg, alpha_1, alpha_2, alpha_3):
    """打印求解结果"""
    print(f"\n{'='*60}")
    print(f"逆解算结果:")
    print(f"{'='*60}")
    print(f"输入参数:")
    print(f"  底边长 b:        {b:.4f} m")
    print(f"  底边角度 theta_0: {theta_0_deg:.2f}°")
    print(f"  灯俯仰角 beta:   {beta_deg:.2f}°")
    print()
    
    print(f"计算的舵机角度:")
    print(f"  alpha_1 (底部):  {alpha_1:.2f}°")
    print(f"  alpha_2 (中间):  {alpha_2:.2f}°")
    print(f"  alpha_3 (顶端):  {alpha_3:.2f}°  (= 180 + {beta_deg:.1f} - {alpha_2:.1f} - {alpha_1:.1f})")
    print()
    
    # 计算编码值
    enc_1 = angle_to_encoder(3, alpha_1)
    enc_2 = angle_to_encoder(2, alpha_2)
    enc_3 = angle_to_encoder(1, alpha_3)
    
    print(f"对应的编码值:")
    print(f"  ID3 (底部): {enc_1:4d}  (范围: {SERVO_CONFIG[3]['zero_pos']}-{SERVO_CONFIG[3]['max_pos']})")
    print(f"  ID2 (中间): {enc_2:4d}  (范围: {SERVO_CONFIG[2]['max_pos']}-{SERVO_CONFIG[2]['zero_pos']})")
    print(f"  ID1 (顶端): {enc_3:4d}  (范围: {SERVO_CONFIG[1]['max_pos']}-{SERVO_CONFIG[1]['zero_pos']})")
    print(f"{'='*60}")
    
    return enc_1, enc_2, enc_3


def read_servo_positions(port_handler, packet_handler):
    """读取所有舵机当前位置（使用同步读取）"""
    from scservo_sdk import GroupSyncRead
    
    # 创建 GroupSyncRead 实例（传入 packet_handler）
    # 起始地址: STS_PRESENT_POSITION_L (56)
    # 数据长度: 2字节 (位置)
    group_sync_read = GroupSyncRead(packet_handler, STS_PRESENT_POSITION_L, 2)
    
    # 添加要读取的舵机ID
    for servo_id in [3, 2, 1]:
        if not group_sync_read.addParam(servo_id):
            print(f"✗ 添加舵机 {servo_id} 读取参数失败")
            return None
    
    # 发送同步读取指令
    result = group_sync_read.txRxPacket()
    
    if result != COMM_SUCCESS:
        print(f"✗ 同步读取失败 (错误码: {result})")
        return None
    
    # 读取数据
    positions = {}
    for servo_id in [3, 2, 1]:
        available, error = group_sync_read.isAvailable(servo_id, STS_PRESENT_POSITION_L, 2)
        if available:
            pos = group_sync_read.getData(servo_id, STS_PRESENT_POSITION_L, 2)
            # 交换字节顺序
            positions[servo_id] = ((pos & 0xFF) << 8) | ((pos >> 8) & 0xFF)
        else:
            print(f"✗ 舵机 {servo_id} 数据不可用")
            return None
    
    return positions


def send_servo_commands(port_handler, packet_handler, enc_1, enc_2, enc_3, speed=200):
    """发送舵机控制指令（使用同步写入）"""
    from scservo_sdk import GroupSyncWrite
    
    print("\n发送舵机指令（同步写入）...")
    
    # 创建 GroupSyncWrite 实例（传入 packet_handler）
    # 起始地址: STS_GOAL_POSITION_L (42)
    # 数据长度: 6字节 (位置2字节 + 时间2字节 + 速度2字节)
    group_sync_write = GroupSyncWrite(packet_handler, STS_GOAL_POSITION_L, 6)
    
    # 准备数据
    encoders = {3: enc_1, 2: enc_2, 1: enc_3}
    
    for servo_id, position in encoders.items():
        # 数据包: [位置高, 位置低, 时间高, 时间低, 速度高, 速度低]
        data = [
            (position >> 8) & 0xFF,  # 位置高字节
            position & 0xFF,         # 位置低字节
            0, 0,                    # 时间（不使用）
            (speed >> 8) & 0xFF,     # 速度高字节
            speed & 0xFF             # 速度低字节
        ]
        
        if not group_sync_write.addParam(servo_id, data):
            print(f"✗ 添加舵机 {servo_id} 参数失败")
            return False
    
    # 发送同步写入指令
    result = group_sync_write.txPacket()
    
    if result == COMM_SUCCESS:
        print("✓ 同步指令发送成功（所有舵机同时启动）")
        return True
    else:
        print(f"✗ 同步指令发送失败 (错误码: {result})")
        return False


def interactive_mode(simulate=True):
    """交互式测试模式"""
    port_handler = None
    packet_handler = None
    
    # 初始化舵机（如果非模拟模式）
    if not simulate:
        if not SERVO_SDK_AVAILABLE:
            print("✗ 舵机库未安装，无法使用真实舵机模式")
            print("  请运行: pip install scservo-sdk")
            return
        
        print("\n正在初始化舵机...")
        port_handler = PortHandler(DEVICE_PORT)
        packet_handler = sms_sts(port_handler)
        
        if not port_handler.openPort():
            print("✗ 串口打开失败")
            return
        
        if not port_handler.setBaudRate(BAUDRATE):
            print("✗ 波特率设置失败")
            return
        
        print("✓ 舵机初始化成功")
    else:
        print("\n[模拟模式] 不会发送真实舵机指令")
    
    print("\n" + "="*60)
    print("台灯连杆逆解算 - 交互式测试")
    print("="*60)
    print(f"\n连杆长度 a = {ARM_LENGTH} m")
    print(f"有效底边范围: 0 < b < {2*ARM_LENGTH} m")
    print()
    print("命令:")
    print("  输入 'b theta_0 [beta]' 测试逆解 (例如: 0.2 45 或 0.2 45 10)")
    print("  beta 默认为 0，正值向下俯，负值向上仰")
    print("  preset - 使用预设参数测试")
    print("  q - 退出")
    print("-"*60)
    
    try:
        while True:
            cmd = input("\n请输入命令: ").strip()
            
            if cmd.lower() in ['q', 'quit', 'exit']:
                break
            
            if cmd.lower() == 'preset':
                test_presets(port_handler, packet_handler, simulate)
                continue
            
            # 解析 b, theta_0, beta
            try:
                parts = cmd.split()
                if len(parts) < 2 or len(parts) > 3:
                    print("✗ 请输入参数: b theta_0 [beta]")
                    continue
                
                b = float(parts[0])
                theta_0_deg = float(parts[1])
                beta_deg = float(parts[2]) if len(parts) > 2 else 0
                
                # 逆解算
                alpha_1, alpha_2, alpha_3, valid = inverse_kinematics(b, theta_0_deg, beta_deg)
                
                if not valid:
                    continue
                
                # 打印结果
                enc_1, enc_2, enc_3 = print_solution(b, theta_0_deg, beta_deg, alpha_1, alpha_2, alpha_3)
                
                # 发送指令
                if not simulate:
                    confirm = input("\n是否发送到舵机? (y/N): ")
                    if confirm.strip().lower() == 'y':
                        send_servo_commands(port_handler, packet_handler, enc_1, enc_2, enc_3)
                        print("  等待舵机运动...")
                        time.sleep(2)
                        
                        # 读取实际位置
                        positions = read_servo_positions(port_handler, packet_handler)
                        if positions:
                            print("\n实际到达位置:")
                            for servo_id, pos in positions.items():
                                print(f"  ID{servo_id}: {pos:4d}")
                
            except ValueError as e:
                print(f"✗ 输入错误: {e}")
            except Exception as e:
                print(f"✗ 错误: {e}")
    
    except KeyboardInterrupt:
        print("\n\n用户中断")
    
    finally:
        if port_handler:
            port_handler.closePort()
            print("\n✓ 串口已关闭")


def test_presets(port_handler, packet_handler, simulate):
    """测试预设参数"""
    presets = [
        {'name': '直立中位', 'b': 0.1, 'theta_0': 90, 'beta': 0},
        {'name': '直立+俯10度', 'b': 0.1, 'theta_0': 90, 'beta': 10},
        {'name': '直立+仰10度', 'b': 0.1, 'theta_0': 90, 'beta': -10},
        {'name': '前倾45度', 'b': 0.15, 'theta_0': 45, 'beta': 0},
        {'name': '后倾135度', 'b': 0.15, 'theta_0': 135, 'beta': 0},
        {'name': '水平0度', 'b': 0.2, 'theta_0': 0, 'beta': 0},
        {'name': '最小间距', 'b': 0.05, 'theta_0': 90, 'beta': 0},
        {'name': '最大间距', 'b': 0.28, 'theta_0': 90, 'beta': 0},
    ]
    
    print("\n" + "="*60)
    print("预设测试:")
    print("="*60)
    
    for i, preset in enumerate(presets, 1):
        print(f"\n[{i}/{len(presets)}] {preset['name']}")
        print("-"*40)
        
        b = preset['b']
        theta_0_deg = preset['theta_0']
        beta_deg = preset.get('beta', 0)
        
        alpha_1, alpha_2, alpha_3, valid = inverse_kinematics(b, theta_0_deg, beta_deg)
        
        if not valid:
            print("  跳过无效配置")
            continue
        
        enc_1, enc_2, enc_3 = print_solution(b, theta_0_deg, beta_deg, alpha_1, alpha_2, alpha_3)
        
        if not simulate:
            confirm = input("\n是否发送到舵机? (y/N/q退出): ")
            if confirm.strip().lower() == 'q':
                break
            if confirm.strip().lower() == 'y':
                send_servo_commands(port_handler, packet_handler, enc_1, enc_2, enc_3)
                print("  等待舵机运动...")
                time.sleep(2)
                
                # 读取实际位置
                positions = read_servo_positions(port_handler, packet_handler)
                if positions:
                    print("\n实际到达位置:")
                    for servo_id, pos in positions.items():
                        print(f"  ID{servo_id}: {pos:4d}")
        else:
            time.sleep(0.5)


def main():
    parser = argparse.ArgumentParser(
        description='台灯连杆逆解算验证脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python test_ik.py --simulate                          # 模拟模式
  python test_ik.py                                     # 真实舵机交互模式
  python test_ik.py -b 0.2 -t 45 --simulate            # 计算指定参数 (beta=0)
  python test_ik.py -b 0.2 -t 45 --beta 10 --simulate  # 计算指定参数 (俯10度)
  python test_ik.py -b 0.2 -t 45 --beta -10            # 计算并发送到舵机 (仰10度)
        """
    )
    
    parser.add_argument(
        '--simulate',
        action='store_true',
        help='模拟模式（不发送真实舵机指令）'
    )
    
    parser.add_argument(
        '-b', '--base',
        type=float,
        help='等腰三角形底边长 (米)'
    )
    
    parser.add_argument(
        '-t', '--theta',
        type=float,
        help='底边角度 theta_0 (度)'
    )
    
    parser.add_argument(
        '--beta',
        type=float,
        default=0,
        help='灯俯仰角 beta (度), 正值向下俯, 负值向上仰, 默认0'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("台灯连杆逆解算验证脚本")
    print("="*60)
    print(f"连杆长度: {ARM_LENGTH} m")
    print(f"编码转换: {ENCODER_PER_DEG:.2f} 编码/度")
    
    # 单次计算模式
    if args.base is not None and args.theta is not None:
        b = args.base
        theta_0_deg = args.theta
        beta_deg = args.beta
        
        alpha_1, alpha_2, alpha_3, valid = inverse_kinematics(b, theta_0_deg, beta_deg)
        
        if not valid:
            if not SERVO_SDK_AVAILABLE:
                print("\n✗ 舵机库未安装，无法发送指令")
                print("  请运行: pip install scservo-sdk")
                return
            
            return
        
        enc_1, enc_2, enc_3 = print_solution(b, theta_0_deg, beta_deg, alpha_1, alpha_2, alpha_3)
        
        if not args.simulate:
            # 初始化舵机
            print("\n正在初始化舵机...")
            port_handler = PortHandler(DEVICE_PORT)
            packet_handler = sms_sts(port_handler)
            
            if not port_handler.openPort():
                print("✗ 串口打开失败")
                return
            
            if not port_handler.setBaudRate(BAUDRATE):
                print("✗ 波特率设置失败")
                return
            
            print("✓ 舵机初始化成功")
            
            try:
                send_servo_commands(port_handler, packet_handler, enc_1, enc_2, enc_3)
                time.sleep(2)
            finally:
                port_handler.closePort()
    else:
        # 交互式模式
        interactive_mode(simulate=args.simulate)


if __name__ == "__main__":
    main()
