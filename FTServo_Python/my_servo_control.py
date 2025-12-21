#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
控制 3 个舵机 (ID: 1, 2, 3) 同时转到指定位置
"""

from scservo_sdk import *
import time

# ========== 配置参数 ==========
DEVICE_PORT = '/dev/ttyUSB0'  # Linux 串口，Windows 改为 'COM1' 等
BAUDRATE = 1000000            # 波特率
SERVO_IDS = [1, 2, 3]         # 舵机 ID 列表
TARGET_POS = 500              # 目标位置 (注意: 舵机角度限制约 20-1003)
SPEED = 500                   # 速度

# 寄存器地址
STS_PRESENT_POSITION_L = 56
STS_GOAL_POSITION_L = 42

# ========== 辅助函数 ==========
def read_position(packet_handler, servo_id):
    """读取舵机位置（交换字节顺序）"""
    pos_raw, result, error = packet_handler.read2ByteTxRx(servo_id, STS_PRESENT_POSITION_L)
    if result == COMM_SUCCESS:
        pos = ((pos_raw & 0xFF) << 8) | ((pos_raw >> 8) & 0xFF)
        return pos, result, error
    return -1, result, error

def write_position(packet_handler, servo_id, position, speed):
    """写入舵机位置和速度（大端序）"""
    # 数据包: 位置高, 位置低, 时间高, 时间低, 速度高, 速度低
    data = [
        (position >> 8) & 0xFF,  # 位置高字节
        position & 0xFF,         # 位置低字节
        0, 0,                    # 时间（不使用）
        (speed >> 8) & 0xFF,     # 速度高字节
        speed & 0xFF             # 速度低字节
    ]
    return packet_handler.writeTxRx(servo_id, STS_GOAL_POSITION_L, len(data), data)

# ========== 初始化 ==========
portHandler = PortHandler(DEVICE_PORT)
packetHandler = sms_sts(portHandler)

# 打开串口
if portHandler.openPort():
    print("串口打开成功")
else:
    print("串口打开失败！")
    quit()

# 设置波特率
if portHandler.setBaudRate(BAUDRATE):
    print("波特率设置成功")
else:
    print("波特率设置失败！")
    quit()

# ========== 同步控制所有舵机 ==========
print(f"控制舵机 {SERVO_IDS} 转到位置 {TARGET_POS}")

# 逐个写入位置
for servo_id in SERVO_IDS:
    write_position(packetHandler, servo_id, TARGET_POS, SPEED)
    time.sleep(0.01)

print("指令已发送！")

# ========== 循环读取舵机位置 ==========
print("\n开始读取舵机位置 (按 Ctrl+C 退出)...")
try:
    while True:
        print("-" * 40)
        
        for servo_id in SERVO_IDS:
            pos, result, error = read_position(packetHandler, servo_id)
            if result == COMM_SUCCESS:
                print(f"[ID:{servo_id}] 位置: {pos:4d}")
            else:
                print(f"[ID:{servo_id}] 通信失败")
            time.sleep(0.05)
            
        time.sleep(0.3)

except KeyboardInterrupt:
    print("\n用户中断")

# ========== 关闭串口 ==========
portHandler.closePort()
print("串口已关闭")
