#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
手部跟随模式 - 独立测试脚本
直接运行: python test_hand_follow.py
"""
import cv2
import sys
import os

# 添加路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 舵机控制配置
SERIAL_PORT = '/dev/ttyUSB0'  # Linux
# SERIAL_PORT = 'COM5'  # Windows
BAUDRATE = 1000000


def main():
    """测试手部跟随模式"""
    print("=" * 50)
    print("手部跟随模式 - 独立测试")
    print("=" * 50)
    print(f"串口: {SERIAL_PORT}")
    print("功能:")
    print("  - 张开手掌: 舵机跟随")
    print("  - 握拳: 暂停跟随")
    print("  - 再次张开: 恢复跟随")
    print("按 'q' 退出测试")
    print()
    
    # 导入模块
    from smart_lamp.modes.hand_follow_mode import (
        HandFollowMode, RealServoController, ServoThread
    )
    
    # 创建舵机控制器
    servo_controller = RealServoController(SERIAL_PORT, BAUDRATE)
    
    # 创建测试用的 controller
    class TestController:
        def __init__(self):
            self.debug = True
            self._servo_thread = None
    
    controller = TestController()
    
    # 尝试连接舵机
    if servo_controller.connect():
        controller._servo_thread = ServoThread(servo_controller)
        print("✓ 舵机连接成功")
    else:
        print("⚠ 舵机连接失败，使用模拟模式")
    
    # 创建模式
    mode = HandFollowMode(controller)
    
    # 打开摄像头
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("错误: 无法打开摄像头")
        return
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    
    # 进入模式
    mode.enter()
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # 更新模式
            mode.update(frame=frame)
            
            # 在画面上显示信息
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
                
                # 显示 openness 和暂停状态
                pause_status = "[PAUSED]" if mode._paused else "[FOLLOW]"
                color = (0, 0, 255) if mode._paused else (0, 255, 0)
                cv2.putText(frame, f"Openness: {openness:.2f} {pause_status}",
                           (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                y += 30
                
                # IK 输入
                cv2.putText(frame, f"IK: [pitch={ik_input[0]:.1f}, y={ik_input[1]:.2f}, dist={ik_input[2]:.2f}]",
                           (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                y += 30
                
                # 当前舵机位置
                enc = mode.current_positions
                cv2.putText(frame, f"Servo: [3:{enc[3]}, 2:{enc[2]}, 1:{enc[1]}]",
                           (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 128, 0), 2)
            else:
                cv2.putText(frame, "No hand detected", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # 提示
            cv2.putText(frame, "Press 'q' to quit | Fist=Pause, Open=Follow",
                       (10, frame.shape[0] - 10),
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
        
        if servo_controller._connected:
            servo_controller.disconnect()
        
        print("测试结束")


if __name__ == "__main__":
    main()
