#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
舵机逆解算测试工具
用于安全测试手部跟随模式的舵机映射
"""

import sys
import time
import numpy as np
from pathlib import Path
from typing import Dict

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))


class ServoIKTester:
    """舵机逆解算测试器"""
    
    def __init__(self, servo_thread=None, simulate=False):
        """
        Args:
            servo_thread: 舵机线程（可选，不提供则模拟）
            simulate: 是否模拟模式（不控制真实舵机）
        """
        self.servo_thread = servo_thread
        self.simulate = simulate
        
        # 舵机配置
        self.servo_ids = [1, 2, 3]
        self.servo_limits = {
            1: (200, 824),   # 底座旋转范围
            2: (300, 724),   # 俯仰1范围
            3: (300, 724),   # 俯仰2范围
        }
        
        # 安全位置
        self.home_position = {1: 512, 2: 512, 3: 512}
        self.current_positions = self.home_position.copy()
        
    def move_to_home(self):
        """移动到安全位置（中位）"""
        print("移动到安全位置（中位）...")
        self._move_servos(self.home_position, speed=100)
        self.current_positions = self.home_position.copy()
        print("✓ 已就位")
    
    def test_single_servo(self, servo_id: int):
        """
        测试单个舵机的全范围运动
        
        Args:
            servo_id: 舵机ID
        """
        if servo_id not in self.servo_ids:
            print(f"✗ 舵机 {servo_id} 不在配置中")
            return
        
        print(f"\n{'='*50}")
        print(f"测试舵机 {servo_id}")
        print(f"{'='*50}")
        
        min_pos, max_pos = self.servo_limits[servo_id]
        center = (min_pos + max_pos) // 2
        
        print(f"范围: {min_pos} - {max_pos}, 中位: {center}")
        print()
        
        # 1. 先回到中位
        print("1. 移动到中位...")
        self._move_servo(servo_id, center, speed=100)
        time.sleep(1)
        
        # 2. 测试最小位置
        print(f"2. 测试最小位置 ({min_pos})...")
        self._move_servo(servo_id, min_pos, speed=50)
        time.sleep(1.5)
        
        # 3. 回到中位
        print("3. 回到中位...")
        self._move_servo(servo_id, center, speed=50)
        time.sleep(1.5)
        
        # 4. 测试最大位置
        print(f"4. 测试最大位置 ({max_pos})...")
        self._move_servo(servo_id, max_pos, speed=50)
        time.sleep(1.5)
        
        # 5. 回到中位
        print("5. 回到中位...")
        self._move_servo(servo_id, center, speed=50)
        time.sleep(1)
        
        print(f"✓ 舵机 {servo_id} 测试完成\n")
    
    def test_all_servos(self):
        """测试所有舵机"""
        print("\n" + "=" * 60)
        print("开始测试所有舵机")
        print("=" * 60)
        
        for servo_id in self.servo_ids:
            self.test_single_servo(servo_id)
            print("等待 2s 后继续...\n")
            time.sleep(2)
        
        print("=" * 60)
        print("所有舵机测试完成")
        print("=" * 60)
    
    def test_inverse_kinematics(self, hand_data: Dict):
        """
        测试逆解算
        
        Args:
            hand_data: 手部数据 {position: [x,y,z], euler: [roll,pitch,yaw], openness: float}
        """
        print("\n" + "-" * 50)
        print("测试逆解算")
        print("-" * 50)
        
        pos = hand_data['position']
        euler = hand_data['euler']
        
        print(f"输入数据:")
        print(f"  Position: [{pos[0]:.3f}, {pos[1]:.3f}, {pos[2]:.3f}]")
        print(f"  Euler:    [{euler[0]:.1f}°, {euler[1]:.1f}°, {euler[2]:.1f}°]")
        print(f"  Openness: {hand_data.get('openness', 0):.2f}")
        print()
        
        # 计算舵机位置
        servo_positions = self._calculate_servo_positions(hand_data)
        
        print(f"计算结果:")
        for servo_id, pos in servo_positions.items():
            min_pos, max_pos = self.servo_limits[servo_id]
            percentage = (pos - min_pos) / (max_pos - min_pos) * 100
            print(f"  舵机{servo_id}: {pos:4d} ({percentage:5.1f}%)")
        print()
        
        # 执行移动
        if input("是否执行此移动? (y/N): ").strip().lower() == 'y':
            print("正在移动...")
            self._move_servos(servo_positions, speed=80)
            self.current_positions = servo_positions.copy()
            print("✓ 移动完成")
        else:
            print("已取消")
    
    def _calculate_servo_positions(self, hand_data: Dict) -> Dict[int, int]:
        """
        根据手部数据计算舵机位置（逆解算）
        
        这是从 hand_follow_mode.py 复制的算法
        """
        pos = hand_data['position']
        euler = hand_data['euler']
        
        yaw = euler[2] if len(euler) > 2 else 0
        pitch = euler[1] if len(euler) > 1 else 0
        z = pos[2] if len(pos) > 2 else 0.5
        
        def map_angle_to_servo(angle, servo_id):
            min_pos, max_pos = self.servo_limits[servo_id]
            center = (min_pos + max_pos) / 2
            half_range = (max_pos - min_pos) / 2
            # -90 ~ 90 -> min ~ max
            normalized = np.clip(angle / 90.0, -1, 1)
            return int(center + normalized * half_range)
        
        def map_distance_to_servo(distance, servo_id):
            min_pos, max_pos = self.servo_limits[servo_id]
            # 0.25m ~ 0.7m -> min ~ max
            normalized = np.clip((distance - 0.25) / 0.45, 0, 1)
            return int(min_pos + normalized * (max_pos - min_pos))
        
        positions = {
            1: map_angle_to_servo(yaw, 1),
            2: map_angle_to_servo(pitch, 2),
            3: map_distance_to_servo(z, 3),
        }
        
        return positions
    
    def interactive_test(self):
        """交互式测试逆解算"""
        print("\n" + "=" * 60)
        print("舵机逆解算 - 交互式测试")
        print("=" * 60)
        
        print("\n命令:")
        print("  home      - 移动到中位")
        print("  servo <id> - 测试单个舵机")
        print("  all       - 测试所有舵机")
        print("  test      - 输入手部数据测试逆解算")
        print("  preset    - 使用预设数据测试")
        print("  q         - 退出")
        print("-" * 60)
        
        while True:
            try:
                cmd = input("\n请输入命令: ").strip()
                
                if cmd.lower() in ['q', 'quit', 'exit']:
                    break
                
                if cmd.lower() == 'home':
                    self.move_to_home()
                    continue
                
                if cmd.lower().startswith('servo'):
                    parts = cmd.split()
                    if len(parts) == 2 and parts[1].isdigit():
                        servo_id = int(parts[1])
                        self.test_single_servo(servo_id)
                    else:
                        print("用法: servo <id>  例如: servo 1")
                    continue
                
                if cmd.lower() == 'all':
                    confirm = input("⚠ 这将测试所有舵机，确认? (y/N): ")
                    if confirm.strip().lower() == 'y':
                        self.test_all_servos()
                    continue
                
                if cmd.lower() == 'test':
                    self._input_hand_data_and_test()
                    continue
                
                if cmd.lower() == 'preset':
                    self._test_with_presets()
                    continue
                
                print(f"✗ 未知命令: '{cmd}'")
                
            except KeyboardInterrupt:
                print("\n\n用户中断")
                break
            except Exception as e:
                print(f"✗ 错误: {e}")
        
        # 退出前回到中位
        print("\n退出前回到中位...")
        self.move_to_home()
        print("测试结束")
    
    def _input_hand_data_and_test(self):
        """输入手部数据并测试"""
        print("\n请输入手部数据:")
        try:
            x = float(input("  Position X (米): "))
            y = float(input("  Position Y (米): "))
            z = float(input("  Position Z (米, 0.25-0.7): "))
            
            roll = float(input("  Euler Roll (度): "))
            pitch = float(input("  Euler Pitch (度, -30~30): "))
            yaw = float(input("  Euler Yaw (度): "))
            
            openness = float(input("  Openness (0-1): "))
            
            hand_data = {
                'position': [x, y, z],
                'euler': [roll, pitch, yaw],
                'openness': openness
            }
            
            self.test_inverse_kinematics(hand_data)
            
        except ValueError as e:
            print(f"✗ 输入错误: {e}")
    
    def _test_with_presets(self):
        """使用预设数据测试"""
        presets = {
            '中位': {
                'position': [0, 0, 0.5],
                'euler': [0, 0, 0],
                'openness': 0.5
            },
            '左侧': {
                'position': [-0.1, 0, 0.5],
                'euler': [0, 0, -45],
                'openness': 0.5
            },
            '右侧': {
                'position': [0.1, 0, 0.5],
                'euler': [0, 0, 45],
                'openness': 0.5
            },
            '近处': {
                'position': [0, 0, 0.25],
                'euler': [0, 0, 0],
                'openness': 0.5
            },
            '远处': {
                'position': [0, 0, 0.7],
                'euler': [0, 0, 0],
                'openness': 0.5
            },
            '抬头': {
                'position': [0, 0, 0.5],
                'euler': [0, 30, 0],
                'openness': 0.5
            },
            '低头': {
                'position': [0, 0, 0.5],
                'euler': [0, -30, 0],
                'openness': 0.5
            },
        }
        
        print("\n预设数据:")
        for i, name in enumerate(presets.keys(), 1):
            print(f"  {i}. {name}")
        
        choice = input("\n选择预设 (编号或名称): ").strip()
        
        # 尝试按编号
        if choice.isdigit():
            idx = int(choice) - 1
            names = list(presets.keys())
            if 0 <= idx < len(names):
                name = names[idx]
                hand_data = presets[name]
                print(f"\n选择: {name}")
                self.test_inverse_kinematics(hand_data)
            else:
                print(f"✗ 编号超出范围")
            return
        
        # 尝试按名称
        if choice in presets:
            self.test_inverse_kinematics(presets[choice])
        else:
            print(f"✗ 未找到预设: '{choice}'")
    
    def _move_servo(self, servo_id: int, position: int, speed: int = None):
        """移动单个舵机"""
        # 限幅
        min_pos, max_pos = self.servo_limits.get(servo_id, (0, 1023))
        position = max(min_pos, min(max_pos, position))
        
        if self.simulate:
            print(f"  [模拟] 舵机{servo_id} -> {position} (速度: {speed})")
        else:
            if self.servo_thread:
                self.servo_thread.set_position(servo_id, position, speed)
            else:
                print(f"  [无舵机] 舵机{servo_id} -> {position}")
        
        self.current_positions[servo_id] = position
    
    def _move_servos(self, positions: Dict[int, int], speed: int = None):
        """移动多个舵机"""
        for servo_id, pos in positions.items():
            self._move_servo(servo_id, pos, speed)


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='舵机逆解算测试工具')
    parser.add_argument(
        '--simulate',
        action='store_true',
        help='模拟模式（不控制真实舵机）'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("舵机逆解算测试工具")
    print("=" * 60)
    
    # 初始化舵机线程
    servo_thread = None
    if not args.simulate:
        print("\n正在初始化舵机...")
        try:
            from smart_lamp.hardware.servo_thread import ServoThread
            servo_thread = ServoThread()
            servo_thread.start()
            time.sleep(0.5)
            print("✓ 舵机初始化成功")
        except Exception as e:
            print(f"⚠ 舵机初始化失败: {e}")
            print("  切换到模拟模式")
            args.simulate = True
    
    # 创建测试器
    tester = ServoIKTester(servo_thread=servo_thread, simulate=args.simulate)
    
    if args.simulate:
        print("\n[模拟模式] 不会控制真实舵机")
    else:
        print("\n⚠ 真实舵机模式 - 请确保舵机已正确连接且机械结构安全")
    
    # 移动到安全位置
    tester.move_to_home()
    
    try:
        tester.interactive_test()
    
    finally:
        # 清理
        if servo_thread:
            print("\n正在停止舵机线程...")
            servo_thread.stop()
            servo_thread.join(timeout=2)
            print("✓ 已停止")


if __name__ == "__main__":
    main()
