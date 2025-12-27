#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试舵机读取 - 使用单独读取方式（更可靠）
"""

import sys
import time
from scservo_sdk import *

# 串口配置
DEVICE_PORT = '/dev/ttyUSB0'  # Linux 串口，Windows 改为 'COM5' 等
BAUDRATE = 1000000
SMS_STS_PRESENT_POSITION_L = 56

def swap_bytes(val):
    """交换高低字节"""
    return ((val & 0xFF) << 8) | ((val >> 8) & 0xFF)

# 初始化
print("初始化舵机...")
portHandler = PortHandler(DEVICE_PORT)
packetHandler = sms_sts(portHandler)

# 打开串口
if portHandler.openPort():
    print("✓ 串口打开成功")
else:
    print("✗ 串口打开失败")
    sys.exit(1)

# 设置波特率
if portHandler.setBaudRate(BAUDRATE):
    print("✓ 波特率设置成功")
else:
    print("✗ 波特率设置失败")
    sys.exit(1)

# 先扫描哪些舵机在线
print("\n扫描舵机...")
available_servos = []
for servo_id in [1, 2, 3]:
    model_number, result, error = packetHandler.ping(servo_id)
    if result == COMM_SUCCESS:
        print(f"✓ ID {servo_id} 在线")
        available_servos.append(servo_id)
    else:
        print(f"✗ ID {servo_id} 离线")

if not available_servos:
    print("\n没有找到任何舵机！")
    sys.exit(1)

print(f"\n找到 {len(available_servos)} 个舵机: {available_servos}")

print("\n开始读取舵机位置 (使用单独读取)...")
print("按 Ctrl+C 退出\n")

try:
    while True:
        print(f"[{time.strftime('%H:%M:%S')}] ", end="")
        
        for scs_id in available_servos:
            # 使用单独读取方式
            pos_raw, result, error = packetHandler.read2ByteTxRx(scs_id, SMS_STS_PRESENT_POSITION_L)
            
            if result == COMM_SUCCESS:
                pos = swap_bytes(pos_raw)
                print(f"ID{scs_id}:{pos:4d} ", end="")
            else:
                print(f"ID{scs_id}:ERR ", end="")
        
        print()
        time.sleep(0.5)

except KeyboardInterrupt:
    print("\n用户中断")

finally:
    portHandler.closePort()
    print("串口已关闭")
