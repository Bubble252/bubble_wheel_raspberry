#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
桌宠动作测试工具
用于逐个测试 actions.yaml 中的动作序列
"""

import sys
import time
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

from smart_lamp.hardware.servo_thread import ServoThread
from smart_lamp.modes.pet_mode import PetMode


class ActionTester:
    """动作测试器"""
    
    def __init__(self, servo_thread=None, simulate=False):
        """
        Args:
            servo_thread: 舵机线程（可选，不提供则模拟）
            simulate: 是否模拟模式（不控制真实舵机）
        """
        self.servo_thread = servo_thread
        self.simulate = simulate
        
        if servo_thread:
            self.actions = servo_thread.actions
        else:
            # 模拟模式：从配置加载动作
            from smart_lamp.utils.config import load_config
            config = load_config()
            self.actions = config.get('actions', {})
        
        self.action_names = list(self.actions.keys()) if self.actions else []
        
    def list_actions(self):
        """列出所有可用动作"""
        print("\n" + "=" * 60)
        print("可用动作列表:")
        print("=" * 60)
        
        if not self.action_names:
            print("  ⚠ 未找到任何动作定义")
            return
        
        for i, action_name in enumerate(self.action_names, 1):
            action = self.actions[action_name]
            duration = self._estimate_duration(action)
            print(f"  {i}. {action_name:<15} (预计时长: {duration:.1f}s)")
        
        print("=" * 60)
        
    def _estimate_duration(self, action) -> float:
        """估算动作时长"""
        if isinstance(action, dict) and 'frames' in action:
            frames = action['frames']
            total_time = sum(frame.get('duration', 0.5) for frame in frames)
            return total_time
        return 0.0
    
    def test_action(self, action_name: str, repeat: int = 1):
        """
        测试单个动作
        
        Args:
            action_name: 动作名称
            repeat: 重复次数
        """
        if action_name not in self.actions:
            print(f"  ✗ 动作 '{action_name}' 不存在")
            return False
        
        action = self.actions[action_name]
        duration = self._estimate_duration(action)
        
        print(f"\n▶ 播放动作: {action_name}")
        print(f"  预计时长: {duration:.1f}s")
        print(f"  重复次数: {repeat}")
        
        if self.simulate:
            # 模拟模式：打印动作信息
            self._print_action_details(action)
            print(f"  [模拟] 等待 {duration * repeat:.1f}s...")
            time.sleep(0.5)  # 短暂延迟，模拟执行
        else:
            # 真实舵机模式
            if not self.servo_thread:
                print("  ✗ 舵机线程未初始化")
                return False
            
            for i in range(repeat):
                if repeat > 1:
                    print(f"  第 {i+1}/{repeat} 次播放...")
                
                self.servo_thread.play_action(action_name)
                
                # 等待动作完成
                time.sleep(duration + 0.5)
        
        print(f"  ✓ 动作完成\n")
        return True
    
    def _print_action_details(self, action):
        """打印动作详情（模拟模式）"""
        if not isinstance(action, dict) or 'frames' not in action:
            print("  动作格式无效")
            return
        
        frames = action['frames']
        print(f"  关键帧数量: {len(frames)}")
        
        for i, frame in enumerate(frames):
            positions = frame.get('positions', {})
            duration = frame.get('duration', 0.5)
            print(f"    Frame {i+1}: {positions} (持续 {duration}s)")
    
    def test_all_actions(self):
        """测试所有动作"""
        print("\n" + "=" * 60)
        print("开始测试所有动作")
        print("=" * 60)
        
        for i, action_name in enumerate(self.action_names, 1):
            print(f"\n[{i}/{len(self.action_names)}] ", end='')
            self.test_action(action_name)
            
            if i < len(self.action_names):
                print("  等待 2s 后继续...")
                time.sleep(2)
        
        print("=" * 60)
        print("所有动作测试完成！")
        print("=" * 60)
    
    def interactive_test(self):
        """交互式测试"""
        print("\n" + "=" * 60)
        print("桌宠动作 - 交互式测试")
        print("=" * 60)
        
        self.list_actions()
        
        print("\n命令:")
        print("  数字     - 播放对应动作")
        print("  名称     - 播放指定动作")
        print("  all      - 测试所有动作")
        print("  list     - 列出所有动作")
        print("  q        - 退出")
        print("-" * 60)
        
        while True:
            try:
                cmd = input("\n请输入命令: ").strip()
                
                if cmd.lower() in ['q', 'quit', 'exit']:
                    print("退出测试")
                    break
                
                if cmd.lower() == 'list':
                    self.list_actions()
                    continue
                
                if cmd.lower() == 'all':
                    self.test_all_actions()
                    continue
                
                # 尝试按编号
                if cmd.isdigit():
                    idx = int(cmd) - 1
                    if 0 <= idx < len(self.action_names):
                        action_name = self.action_names[idx]
                        self.test_action(action_name)
                    else:
                        print(f"  ✗ 编号超出范围 (1-{len(self.action_names)})")
                    continue
                
                # 尝试按名称
                if cmd in self.action_names:
                    self.test_action(cmd)
                else:
                    print(f"  ✗ 未知命令或动作: '{cmd}'")
                    
            except KeyboardInterrupt:
                print("\n\n用户中断")
                break
            except Exception as e:
                print(f"  ✗ 错误: {e}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='桌宠动作测试工具')
    parser.add_argument(
        '--simulate',
        action='store_true',
        help='模拟模式（不控制真实舵机）'
    )
    parser.add_argument(
        '--action',
        type=str,
        help='测试指定动作'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='测试所有动作'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("桌宠动作测试工具")
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
    tester = ActionTester(servo_thread=servo_thread, simulate=args.simulate)
    
    if args.simulate:
        print("\n[模拟模式] 不会控制真实舵机")
    
    try:
        if args.action:
            # 测试指定动作
            tester.test_action(args.action)
        elif args.all:
            # 测试所有动作
            tester.test_all_actions()
        else:
            # 交互式测试
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
