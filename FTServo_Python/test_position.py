#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试舵机写入和读取
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

servo_id = 1
STS_PRESENT_POSITION_L = 56
STS_GOAL_POSITION_L = 42

def read_pos():
    """读取舵机位置（交换字节）"""
    pos_raw, result, error = packetHandler.read2ByteTxRx(servo_id, STS_PRESENT_POSITION_L)
    return ((pos_raw & 0xFF) << 8) | ((pos_raw >> 8) & 0xFF)

def write_pos_with_speed(scs_id, position, speed):
    """写入目标位置和速度（地址42-47）- 大端序"""
    # 数据包: 位置高, 位置低, 时间高, 时间低, 速度高, 速度低
    data = [
        (position >> 8) & 0xFF,  # 位置高字节
        position & 0xFF,         # 位置低字节
        0,                       # 时间高字节
        0,                       # 时间低字节
        (speed >> 8) & 0xFF,     # 速度高字节
        speed & 0xFF             # 速度低字节
    ]
    return packetHandler.writeTxRx(scs_id, STS_GOAL_POSITION_L, len(data), data)

# 读取舵机角度限制
STS_MIN_ANGLE_LIMIT_L = 9
STS_MAX_ANGLE_LIMIT_L = 11

print("=" * 50)
min_raw, _, _ = packetHandler.read2ByteTxRx(servo_id, STS_MIN_ANGLE_LIMIT_L)
max_raw, _, _ = packetHandler.read2ByteTxRx(servo_id, STS_MAX_ANGLE_LIMIT_L)
min_angle = ((min_raw & 0xFF) << 8) | ((min_raw >> 8) & 0xFF)
max_angle = ((max_raw & 0xFF) << 8) | ((max_raw >> 8) & 0xFF)
print(f"角度限制: {min_angle} - {max_angle}")
print("当前位置:", read_pos())

# 测试 1: 目标位置 2048
print("\n测试1: 写入位置 1500, 速度 500")
write_pos_with_speed(servo_id, 1500, 500)
time.sleep(2)
print("实际位置:", read_pos())

# 测试 2: 目标位置 500
print("\n测试2: 写入位置 500, 速度 500")
write_pos_with_speed(servo_id, 500, 500)
time.sleep(2)
print("实际位置:", read_pos())

# 测试 3: 目标位置 1000
print("\n测试3: 写入位置 1000, 速度 500")
write_pos_with_speed(servo_id, 1000, 500)
time.sleep(2)
print("实际位置:", read_pos())

# 测试 4: 目标位置 100
print("\n测试4: 写入位置 100, 速度 500")
write_pos_with_speed(servo_id, 100, 500)
time.sleep(2)
print("实际位置:", read_pos())

# 测试 5: 目标位置 0
print("\n测试5: 写入位置 0, 速度 500")
write_pos_with_speed(servo_id, 0, 500)
time.sleep(2)
print("实际位置:", read_pos())

portHandler.closePort()
print("\n测试完成")
