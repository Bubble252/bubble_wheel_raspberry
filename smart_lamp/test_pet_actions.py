#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桌宠动作测试工具 (支持逆解参数)

支持两种模式:
1. 播放 actions.yaml 中定义的动作
2. 直接输入 b, theta_0, beta 参数测试姿态

用法:
    python test_pet_actions.py [--simulate] [--action NAME] [--all]
    python test_pet_actions.py --pose 0.1 90 0   # 直接测试姿态
"""

import os
import sys
import time
import argparse
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

# 导入逆解算模块
from smart_lamp.utils.kinematics import (
    pose_to_encoders, 
    inverse_kinematics,
    get_home_encoders,
    SERVO_CONFIG,
    SERVO_LIMITS,
)

# 舵机配置
SERIAL_PORT = '/dev/ttyUSB0'
BAUDRATE = 1000000


class RealServoController:
    """真实舵机控制器"""
    
    STS_GOAL_POSITION_L = 42
    
    def __init__(self, port=SERIAL_PORT, baudrate=BAUDRATE):
        self.port = port
        self.baudrate = baudrate
        self.port_handler = None
        self.packet_handler = None
        self._connected = False
        
    def connect(self) -> bool:
        """连接舵机"""
        try:
            # 添加 scservo_sdk 路径
            sdk_path = os.path.join(PROJECT_ROOT, 'scservo_sdk')
            sys.path.insert(0, sdk_path)
            
            from scservo_sdk import PortHandler, sms_sts, COMM_SUCCESS
            
            self.COMM_SUCCESS = COMM_SUCCESS
            
            self.port_handler = PortHandler(self.port)
            if not self.port_handler.openPort():
                print(f"✗ 无法打开串口: {self.port}")
                return False
            
            if not self.port_handler.setBaudRate(self.baudrate):
                print(f"✗ 无法设置波特率: {self.baudrate}")
                return False
            
            self.packet_handler = sms_sts(self.port_handler)
            self._connected = True
            print(f"✓ 舵机连接成功: {self.port}")
            return True
            
        except ImportError as e:
            print(f"✗ scservo_sdk 导入失败: {e}")
            return False
        except Exception as e:
            print(f"✗ 连接失败: {e}")
            return False
    
    def disconnect(self):
        """断开连接"""
        if self.port_handler:
            self.port_handler.closePort()
            self._connected = False
            print("舵机已断开连接")
    
    def move(self, servo_id: int, position: int, speed: int = 500):
        """移动单个舵机"""
        if not self._connected:
            return
        
        position = max(0, min(1023, position))
        
        data = [
            (position >> 8) & 0xFF,
            position & 0xFF,
            0, 0,
            (speed >> 8) & 0xFF,
            speed & 0xFF
        ]
        
        try:
            self.packet_handler.writeTxRx(servo_id, self.STS_GOAL_POSITION_L, len(data), data)
        except Exception as e:
            print(f"写入舵机 {servo_id} 失败: {e}")
    
    def sync_move(self, positions: dict, speed: int = 500):
        """同步移动多个舵机"""
        for servo_id, pos in positions.items():
            self.move(servo_id, pos, speed)


class MockServoController:
    """模拟舵机控制器"""
    
    def connect(self) -> bool:
        print("✓ 模拟模式: 舵机已连接")
        return True
    
    def disconnect(self):
        print("模拟模式: 舵机已断开")
    
    def move(self, servo_id: int, position: int, speed: int = 500):
        pass
    
    def sync_move(self, positions: dict, speed: int = 500):
        pass


class ActionTester:
    """动作测试器"""
    
    def __init__(self, servo, simulate=False):
        self.servo = servo
        self.simulate = simulate
        self.actions = {}
        self._load_actions()
    
    def _load_actions(self):
        """加载动作配置"""
        import yaml
        
        actions_file = PROJECT_ROOT / 'config' / 'actions.yaml'
        if actions_file.exists():
            with open(actions_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.actions = config.get('actions', {})
            print(f"加载了 {len(self.actions)} 个动作")
        else:
            print(f"⚠ 动作配置文件不存在: {actions_file}")
    
    def list_actions(self):
        """列出所有动作"""
        print("\n" + "=" * 60)
        print("可用动作列表:")
        print("=" * 60)
        
        for i, (name, action) in enumerate(self.actions.items(), 1):
            desc = action.get('description', '')
            duration = action.get('duration', 0)
            loop = '🔁' if action.get('loop', False) else ''
            print(f"  {i:2}. {name:<12} {loop} ({duration}ms) - {desc}")
        
        print("=" * 60)
    
    def test_pose(self, b: float, theta_0: float, beta: float, speed: int = 300):
        """
        测试单个姿态
        
        Args:
            b: 底边长 (米)
            theta_0: 底边角度 (度)
            beta: 俯仰角 (度)
            speed: 移动速度
        """
        print(f"\n▶ 测试姿态: b={b:.3f}m, θ₀={theta_0}°, β={beta}°")
        
        # 计算逆解
        alpha_1, alpha_2, alpha_3, valid = inverse_kinematics(b, theta_0, beta)
        
        if not valid:
            print(f"  ✗ 无效姿态！角度超出范围")
            return False
        
        positions, _ = pose_to_encoders(b, theta_0, beta)
        
        print(f"  逆解角度: α₁={alpha_1:.1f}° (底), α₂={alpha_2:.1f}° (中), α₃={alpha_3:.1f}° (顶)")
        print(f"  编码值: ID3={positions[3]}, ID2={positions[2]}, ID1={positions[1]}")
        
        if self.simulate:
            print(f"  [模拟] 移动到位置")
        else:
            self.servo.sync_move(positions, speed)
            print(f"  ✓ 已移动")
        
        return True
    
    def test_action(self, action_name: str, force_loop: bool = None):
        """测试动作
        
        Args:
            action_name: 动作名称
            force_loop: 强制循环设置，None表示使用yaml配置
        """
        if action_name not in self.actions:
            print(f"  ✗ 动作 '{action_name}' 不存在")
            return False
        
        action = self.actions[action_name]
        name = action.get('name', action_name)
        desc = action.get('description', '')
        duration = action.get('duration', 0)
        loop = action.get('loop', False) if force_loop is None else force_loop
        keyframes = action.get('keyframes', [])
        
        print(f"\n▶ 播放动作: {name}")
        print(f"  描述: {desc}")
        print(f"  时长: {duration}ms, 循环: {loop}")
        print(f"  关键帧数: {len(keyframes)}")
        if loop:
            print(f"  [提示] 按 Ctrl+C 停止循环")
        print()
        
        try:
            loop_count = 0
            while True:
                loop_count += 1
                if loop:
                    print(f"  --- 第 {loop_count} 次循环 ---")
                
                # 播放关键帧
                for i, kf in enumerate(keyframes):
                    kf_time = kf.get('time', 0)
                    
                    # 获取姿态参数
                    if 'pose' in kf:
                        pose = kf['pose']
                        b = pose.get('b', 0.1)
                        theta_0 = pose.get('theta_0', 90)
                        beta = pose.get('beta', 0)
                        
                        positions, valid = pose_to_encoders(b, theta_0, beta)
                        
                        if not valid:
                            print(f"  [{kf_time}ms] ✗ 无效姿态: b={b}, θ₀={theta_0}, β={beta}")
                            continue
                        
                        print(f"  [{kf_time}ms] pose: b={b:.2f}, θ₀={theta_0}, β={beta} → "
                              f"enc: [{positions[3]}, {positions[2]}, {positions[1]}]")
                    
                    elif 'positions' in kf:
                        # 旧格式
                        positions = {int(k): v for k, v in kf['positions'].items()}
                        print(f"  [{kf_time}ms] positions: {positions}")
                    
                    else:
                        print(f"  [{kf_time}ms] ✗ 无效关键帧格式")
                        continue
                    
                    # 移动舵机
                    if not self.simulate:
                        self.servo.sync_move(positions, speed=500)
                    
                    # 等待到下一帧
                    if i < len(keyframes) - 1:
                        next_time = keyframes[i + 1].get('time', 0)
                        wait_ms = next_time - kf_time
                        if wait_ms > 0:
                            time.sleep(wait_ms / 1000.0)
                
                # 如果不循环，退出
                if not loop:
                    break
                    
        except KeyboardInterrupt:
            print(f"\n  ⏹ 循环已停止 (共 {loop_count} 次)")
        
        print(f"\n  ✓ 动作完成")
        return True
    
    def test_all(self):
        """测试所有动作"""
        print("\n" + "=" * 60)
        print("测试所有动作")
        print("=" * 60)
        
        for name in self.actions.keys():
            self.test_action(name)
            time.sleep(1)
            
            # 回到初始位置
            self.go_home()
            time.sleep(0.5)
        
        print("\n✓ 所有动作测试完成")
    
    def go_home(self):
        """回到初始位置"""
        print("→ 归位中...")
        home = get_home_encoders()
        
        if self.simulate:
            print(f"  [模拟] home: {home}")
        else:
            self.servo.sync_move(home, speed=300)
        
        time.sleep(0.5)
    
    def interactive(self):
        """交互式测试"""
        print("\n" + "=" * 60)
        print("交互式测试模式")
        print("=" * 60)
        
        self.list_actions()
        
        print("\n命令:")
        print("  <数字>                - 播放对应编号的动作")
        print("  <动作名>              - 播放指定动作")
        print("  pose <b> <θ₀> <β>     - 测试指定姿态")
        print("  home                  - 回到初始位置")
        print("  list                  - 列出所有动作")
        print("  all                   - 测试所有动作")
        print("  q                     - 退出")
        print("-" * 60)
        
        action_names = list(self.actions.keys())
        
        while True:
            try:
                cmd = input("\n> ").strip()
                
                if not cmd:
                    continue
                
                if cmd.lower() in ['q', 'quit', 'exit']:
                    print("退出")
                    break
                
                if cmd.lower() == 'list':
                    self.list_actions()
                    continue
                
                if cmd.lower() == 'all':
                    self.test_all()
                    continue
                
                if cmd.lower() == 'home':
                    self.go_home()
                    continue
                
                # pose 命令
                if cmd.lower().startswith('pose'):
                    parts = cmd.split()
                    if len(parts) >= 4:
                        try:
                            b = float(parts[1])
                            theta_0 = float(parts[2])
                            beta = float(parts[3])
                            self.test_pose(b, theta_0, beta)
                        except ValueError:
                            print("  ✗ 参数格式错误: pose <b> <theta_0> <beta>")
                    else:
                        print("  用法: pose <b> <theta_0> <beta>")
                        print("  例如: pose 0.1 90 0")
                    continue
                
                # 数字编号
                if cmd.isdigit():
                    idx = int(cmd) - 1
                    if 0 <= idx < len(action_names):
                        self.test_action(action_names[idx])
                    else:
                        print(f"  ✗ 编号超出范围 (1-{len(action_names)})")
                    continue
                
                # 动作名
                if cmd in self.actions:
                    self.test_action(cmd)
                else:
                    print(f"  ✗ 未知命令: '{cmd}'")
                    
            except KeyboardInterrupt:
                print("\n\n中断")
                break
            except Exception as e:
                print(f"  ✗ 错误: {e}")


def main():
    parser = argparse.ArgumentParser(
        description='桌宠动作测试工具 (支持逆解参数)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s                      # 交互式测试
  %(prog)s --simulate           # 模拟模式（不控制舵机）
  %(prog)s --action nod         # 测试指定动作 (根据yaml的loop字段循环)
  %(prog)s --action nod --no-loop  # 测试动作但不循环
  %(prog)s --all                # 测试所有动作
  %(prog)s --pose 0.2 90 0      # 测试指定姿态 (b, theta_0, beta)
        """
    )
    parser.add_argument('--simulate', action='store_true', help='模拟模式')
    parser.add_argument('--action', type=str, help='测试指定动作')
    parser.add_argument('--no-loop', action='store_true', help='强制不循环（忽略yaml的loop字段）')
    parser.add_argument('--all', action='store_true', help='测试所有动作')
    parser.add_argument('--pose', nargs=3, type=float, metavar=('B', 'THETA0', 'BETA'),
                        help='测试指定姿态')
    parser.add_argument('--port', type=str, default=SERIAL_PORT, help='串口')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("桌宠动作测试工具 (逆解参数版)")
    print("=" * 60)
    
    # 初始化舵机
    if args.simulate:
        servo = MockServoController()
        servo.connect()
    else:
        servo = RealServoController(args.port, BAUDRATE)
        if not servo.connect():
            print("⚠ 舵机连接失败，切换到模拟模式")
            servo = MockServoController()
            servo.connect()
            args.simulate = True
    
    tester = ActionTester(servo, simulate=args.simulate)
    
    try:
        # 先归位
        tester.go_home()
        
        if args.pose:
            # 测试指定姿态
            b, theta_0, beta = args.pose
            tester.test_pose(b, theta_0, beta)
        elif args.action:
            # 测试指定动作
            force_loop = False if args.no_loop else None
            tester.test_action(args.action, force_loop=force_loop)
        elif args.all:
            # 测试所有动作
            tester.test_all()
        else:
            # 交互式
            tester.interactive()
        
        # 结束时归位
        tester.go_home()
        
    except KeyboardInterrupt:
        print("\n\n用户中断")
    finally:
        servo.disconnect()
        print("\n测试结束")


if __name__ == "__main__":
    main()
