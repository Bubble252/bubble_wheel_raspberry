#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
扫描所有连接的舵机
"""

from scservo_sdk import *

# ========== 配置参数 ==========
DEVICE_PORT = '/dev/ttyUSB0'  # 串口
BAUDRATE = 1000000            # 波特率，常见的有: 1000000, 500000, 115200

# ========== 初始化 ==========
portHandler = PortHandler(DEVICE_PORT)
packetHandler = sms_sts(portHandler)

# 打开串口
if portHandler.openPort():
    print("串口打开成功")
else:
    print("串口打开失败！请检查串口连接")
    quit()

# 设置波特率
if portHandler.setBaudRate(BAUDRATE):
    print(f"波特率设置成功: {BAUDRATE}")
else:
    print("波特率设置失败！")
    quit()

# ========== 扫描舵机 ==========
print("\n开始扫描舵机 (ID: 1-20)...")
print("-" * 40)

found_servos = []

for servo_id in range(1, 21):  # 扫描 ID 1-20
    model_number, result, error = packetHandler.ping(servo_id)
    if result == COMM_SUCCESS:
        print(f"[ID:{servo_id:2d}] ✓ 找到舵机! 型号: {model_number}")
        found_servos.append(servo_id)

print("-" * 40)
if found_servos:
    print(f"共找到 {len(found_servos)} 个舵机: {found_servos}")
else:
    print("没有找到任何舵机！")
    print("\n可能的原因:")
    print("1. 舵机没有上电")
    print("2. 串口连接不正确")
    print("3. 波特率不匹配 (尝试修改 BAUDRATE 为 500000 或 115200)")
    print("4. 舵机线路接反或接触不良")

# 关闭串口
portHandler.closePort()
print("\n串口已关闭")
