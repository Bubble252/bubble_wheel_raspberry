#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
调试舵机读取 - 使用底层读取方式
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

# 测试读取 ID 1 的舵机
servo_id = 1

print(f"=== 测试舵机 ID:{servo_id} ===\n")

# 1. 先 ping 确认舵机在线
print("1. Ping 测试:")
model, result, error = packetHandler.ping(servo_id)
if result == COMM_SUCCESS:
    print(f"   ✓ 舵机在线, 型号: {model}")
else:
    print(f"   ✗ Ping 失败: {packetHandler.getTxRxResult(result)}")
    portHandler.closePort()
    quit()

time.sleep(0.1)

# 2. 读取当前位置 (地址 56-57)
print("\n2. 读取位置 (read2ByteTxRx):")
pos_raw, result, error = packetHandler.read2ByteTxRx(servo_id, 56)
print(f"   原始值: {pos_raw}, 结果: {result}, 错误: {error}")
if result == COMM_SUCCESS:
    print(f"   位置值: {pos_raw}")

time.sleep(0.1)

# 3. 使用 ReadPos 函数
print("\n3. 使用 ReadPos 函数:")
pos, result, error = packetHandler.ReadPos(servo_id)
print(f"   位置: {pos}, 结果: {result}, 错误: {error}")

time.sleep(0.1)

# 4. 读取 Moving 状态
print("\n4. 读取 Moving 状态:")
moving, result, error = packetHandler.ReadMoving(servo_id)
print(f"   Moving: {moving}, 结果: {result}, 错误: {error}")

time.sleep(0.1)

# 5. 尝试写入位置并读回
print("\n5. 写入位置 2048 并读回:")
packetHandler.WritePosEx(servo_id, 2048, 100, 50)
time.sleep(1)  # 等待舵机移动

pos, result, error = packetHandler.ReadPos(servo_id)
print(f"   读取位置: {pos}, 结果: {result}")

portHandler.closePort()
print("\n测试完成")
