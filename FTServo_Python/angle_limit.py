#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
读取和设置舵机角度限制
"""

from scservo_sdk import *
import time

DEVICE_PORT = '/dev/ttyUSB0'
BAUDRATE = 1000000

portHandler = PortHandler(DEVICE_PORT)
packetHandler = sms_sts(portHandler)

if not portHandler.openPort():
    print("串口打开失败！")
    quit()

if not portHandler.setBaudRate(BAUDRATE):
    print("波特率设置失败！")
    quit()

print("串口初始化成功\n")

# 寄存器地址
STS_MIN_ANGLE_LIMIT_L = 9   # 最小角度限制 (地址 9-10)
STS_MAX_ANGLE_LIMIT_L = 11  # 最大角度限制 (地址 11-12)
STS_LOCK = 55               # EPROM 锁定寄存器

def swap_bytes(val):
    """交换高低字节"""
    return ((val & 0xFF) << 8) | ((val >> 8) & 0xFF)

def read_angle_limits(servo_id):
    """读取舵机角度限制"""
    min_raw, _, _ = packetHandler.read2ByteTxRx(servo_id, STS_MIN_ANGLE_LIMIT_L)
    max_raw, _, _ = packetHandler.read2ByteTxRx(servo_id, STS_MAX_ANGLE_LIMIT_L)
    return swap_bytes(min_raw), swap_bytes(max_raw)

def set_angle_limits(servo_id, min_angle, max_angle):
    """设置舵机角度限制 (需要解锁 EPROM)"""
    # 1. 解锁 EPROM
    packetHandler.write1ByteTxRx(servo_id, STS_LOCK, 0)
    time.sleep(0.1)
    
    # 2. 写入最小角度 (大端序)
    data_min = [(min_angle >> 8) & 0xFF, min_angle & 0xFF]
    packetHandler.writeTxRx(servo_id, STS_MIN_ANGLE_LIMIT_L, 2, data_min)
    time.sleep(0.1)
    
    # 3. 写入最大角度 (大端序)
    data_max = [(max_angle >> 8) & 0xFF, max_angle & 0xFF]
    packetHandler.writeTxRx(servo_id, STS_MAX_ANGLE_LIMIT_L, 2, data_max)
    time.sleep(0.1)
    
    # 4. 锁定 EPROM
    packetHandler.write1ByteTxRx(servo_id, STS_LOCK, 1)
    time.sleep(0.1)

# ========== 读取所有舵机的角度限制 ==========
print("=" * 50)
print("当前舵机角度限制:")
print("=" * 50)

for servo_id in [1, 2, 3]:
    min_angle, max_angle = read_angle_limits(servo_id)
    print(f"[ID:{servo_id}] 角度范围: {min_angle} - {max_angle}")

print("\n说明:")
print("  - 位置范围通常是 0-4095 (对应 0°-360°)")
print("  - 当前限制约为 20-1003，即约 1.8°-88°")

# ========== 如果需要修改角度限制，取消下面的注释 ==========
# print("\n修改舵机角度限制...")
# 
# # 设置新的角度范围 (例如: 0-4095 全范围)
# NEW_MIN = 0
# NEW_MAX = 4095
# 
# for servo_id in [1, 2, 3]:
#     set_angle_limits(servo_id, NEW_MIN, NEW_MAX)
#     print(f"[ID:{servo_id}] 已设置角度范围: {NEW_MIN} - {NEW_MAX}")
# 
# # 验证修改
# print("\n验证修改后的角度限制:")
# for servo_id in [1, 2, 3]:
#     min_angle, max_angle = read_angle_limits(servo_id)
#     print(f"[ID:{servo_id}] 角度范围: {min_angle} - {max_angle}")

portHandler.closePort()
print("\n完成")
