#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
读取所有舵机状态（只读不写）
- 当前位置
- 角度限制（最小/最大）
"""

from scservo_sdk import *
import time

# ========== 配置参数 ==========
DEVICE_PORT = '/dev/ttyUSB0'  # Linux 串口，Windows 改为 'COM3' 等
BAUDRATE = 1000000            # 波特率
SERVO_IDS = [1, 2, 3]         # 舵机 ID 列表

# 寄存器地址
STS_PRESENT_POSITION_L = 56   # 当前位置
STS_MIN_ANGLE_LIMIT_L = 9     # 最小角度限制
STS_MAX_ANGLE_LIMIT_L = 11    # 最大角度限制

# ========== 辅助函数 ==========
def swap_bytes(val):
    """交换高低字节"""
    return ((val & 0xFF) << 8) | ((val >> 8) & 0xFF)

def read_position(packet_handler, servo_id):
    """读取舵机当前位置"""
    pos_raw, result, error = packet_handler.read2ByteTxRx(servo_id, STS_PRESENT_POSITION_L)
    if result == COMM_SUCCESS:
        pos = swap_bytes(pos_raw)
        return pos, True
    return -1, False

def read_angle_limits(packet_handler, servo_id):
    """读取舵机角度限制"""
    min_raw, result1, _ = packet_handler.read2ByteTxRx(servo_id, STS_MIN_ANGLE_LIMIT_L)
    max_raw, result2, _ = packet_handler.read2ByteTxRx(servo_id, STS_MAX_ANGLE_LIMIT_L)
    
    if result1 == COMM_SUCCESS and result2 == COMM_SUCCESS:
        return swap_bytes(min_raw), swap_bytes(max_raw), True
    return -1, -1, False

# ========== 初始化 ==========
portHandler = PortHandler(DEVICE_PORT)
packetHandler = sms_sts(portHandler)

# 打开串口
if not portHandler.openPort():
    print("✗ 串口打开失败！")
    print(f"  请检查设备路径: {DEVICE_PORT}")
    quit()

print("✓ 串口打开成功")

# 设置波特率
if not portHandler.setBaudRate(BAUDRATE):
    print("✗ 波特率设置失败！")
    quit()

print("✓ 波特率设置成功")
print()

# ========== 读取角度限制（一次性） ==========
print("=" * 60)
print("舵机角度限制:")
print("=" * 60)

servo_info = {}

for servo_id in SERVO_IDS:
    min_angle, max_angle, success = read_angle_limits(packetHandler, servo_id)
    
    if success:
        print(f"[ID:{servo_id}] 角度范围: {min_angle:4d} - {max_angle:4d}  " +
              f"(范围: {max_angle - min_angle:4d})")
        servo_info[servo_id] = {'min': min_angle, 'max': max_angle}
    else:
        print(f"[ID:{servo_id}] 读取失败 - 请检查连接和ID")
        servo_info[servo_id] = {'min': -1, 'max': -1}

print()
print("说明:")
print("  - 理论全范围: 0-4095 (对应 0°-360°)")
print("  - 建议设置范围以避免机械冲突")

# ========== 持续读取当前位置 ==========
print("\n" + "=" * 60)
print("舵机当前位置 (按 Ctrl+C 退出):")
print("=" * 60)
print()

try:
    while True:
        positions = []
        
        # 读取所有舵机位置
        for servo_id in SERVO_IDS:
            pos, success = read_position(packetHandler, servo_id)
            
            if success:
                min_angle = servo_info[servo_id]['min']
                max_angle = servo_info[servo_id]['max']
                
                # 计算百分比
                if min_angle >= 0 and max_angle > min_angle:
                    percentage = (pos - min_angle) / (max_angle - min_angle) * 100
                    percentage = max(0, min(100, percentage))
                else:
                    percentage = 0
                
                positions.append(f"[ID:{servo_id}] {pos:4d} ({percentage:5.1f}%)")
            else:
                positions.append(f"[ID:{servo_id}] 通信失败")
        
        # 打印同一行
        print("\r" + "  |  ".join(positions), end='', flush=True)
        
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\n\n用户中断")

# ========== 关闭串口 ==========
portHandler.closePort()
print("✓ 串口已关闭")
