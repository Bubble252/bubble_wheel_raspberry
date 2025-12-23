#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能台灯 - 主入口文件

启动方式:
    python run.py                    # 正常启动全部功能
    python run.py --debug            # 调试模式
    python run.py --mode hand        # 直接进入手部跟随模式
    python run.py --mode pet         # 直接进入桌宠模式
    python run.py --mode brightness  # 直接进入亮度调节模式
    python run.py --no-servo         # 接入摄像头和麦克风，但不接舵机
    python run.py --simulate         # 纯模拟模式（键盘输入）
    python run.py --test-voice       # 测试语音模块
    python run.py --test-servo       # 测试舵机模块
    python run.py --test-camera      # 测试摄像头
"""

import sys
import argparse
import signal
import time
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='智能台灯控制系统',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py                    启动完整系统
  python run.py --mode pet         直接进入桌宠模式
  python run.py --mode hand        直接进入手部跟随模式
  python run.py --test-servo       测试舵机连接
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        type=str,
        default='config/config.yaml',
        help='配置文件路径 (默认: config/config.yaml)'
    )
    
    parser.add_argument(
        '-d', '--debug',
        action='store_true',
        help='启用调试模式'
    )
    
    parser.add_argument(
        '-m', '--mode',
        type=str,
        choices=['hand', 'pet', 'brightness'],
        help='直接进入指定模式 (跳过唤醒词)'
    )
    
    parser.add_argument(
        '--test-servo',
        action='store_true',
        help='测试舵机连接'
    )
    
    parser.add_argument(
        '--test-camera',
        action='store_true',
        help='测试摄像头'
    )
    
    parser.add_argument(
        '--test-voice',
        action='store_true',
        help='测试语音识别'
    )
    
    parser.add_argument(
        '--simulate',
        action='store_true',
        help='纯模拟模式（键盘输入，不连接任何硬件）'
    )
    
    parser.add_argument(
        '--no-servo',
        action='store_true',
        help='半模拟模式（接入摄像头和麦克风，但舵机只打印不执行）'
    )
    
    parser.add_argument(
        '--no-voice',
        action='store_true',
        help='禁用语音（只用摄像头和舵机）'
    )
    
    parser.add_argument(
        '--version',
        action='store_true',
        help='显示版本号'
    )
    
    return parser.parse_args()


def show_version():
    """显示版本信息"""
    print("智能台灯控制系统 v2.0.0")
    print("架构: 模式切换系统")
    print("模式: 手部跟随 | 桌宠 | 亮度调节")


def test_servo(config_path: str):
    """测试舵机连接"""
    print("=" * 50)
    print("舵机连接测试")
    print("=" * 50)
    
    from smart_lamp.utils.config_loader import load_config
    config = load_config(config_path)
    
    try:
        from smart_lamp.modules.servo.servo_driver import ServoDriver
        driver = ServoDriver(config.get('servo', {}))
        
        if driver.connect():
            print("✓ 舵机连接成功")
            
            # 读取位置
            for servo_id in [1, 2, 3]:
                pos = driver.read_position(servo_id)
                if pos is not None:
                    print(f"  舵机 {servo_id}: 位置 {pos}")
                else:
                    print(f"  舵机 {servo_id}: 读取失败")
            
            # 移动测试
            input("\n按 Enter 执行归中测试...")
            print("移动到中位 (512)...")
            driver.sync_move({1: 512, 2: 512, 3: 512}, speed=100)
            time.sleep(1)
            
            driver.disconnect()
            print("\n✓ 测试完成")
        else:
            print("✗ 舵机连接失败")
            
    except Exception as e:
        print(f"✗ 测试失败: {e}")


def test_camera(config_path: str):
    """测试摄像头"""
    print("=" * 50)
    print("摄像头测试")
    print("=" * 50)
    
    import cv2
    
    from smart_lamp.utils.config_loader import load_config
    config = load_config(config_path)
    
    camera_index = config.get('camera', {}).get('index', 0)
    
    cap = cv2.VideoCapture(camera_index)
    
    if cap.isOpened():
        print(f"✓ 摄像头 {camera_index} 打开成功")
        
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        
        print(f"  分辨率: {width}x{height}")
        print(f"  帧率: {fps} FPS")
        
        print("\n按 'q' 退出预览...")
        
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            cv2.putText(frame, f"Camera Test - Press 'q' to quit",
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow("Camera Test", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
        
        cap.release()
        cv2.destroyAllWindows()
        print("\n✓ 测试完成")
    else:
        print(f"✗ 摄像头 {camera_index} 打开失败")


def test_voice(config_path: str):
    """测试语音识别"""
    print("=" * 50)
    print("语音识别测试")
    print("=" * 50)
    
    try:
        import pyaudio
        
        p = pyaudio.PyAudio()
        
        print("\n可用音频设备:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                print(f"  [{i}] {info['name']}")
        
        print("\n开始 5 秒录音测试...")
        
        stream = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=1024
        )
        
        frames = []
        for i in range(int(16000 / 1024 * 5)):
            data = stream.read(1024, exception_on_overflow=False)
            frames.append(data)
            # 简单的音量显示
            if i % 10 == 0:
                print(".", end="", flush=True)
        
        print()
        
        stream.stop_stream()
        stream.close()
        p.terminate()
        
        print("✓ 录音成功")
        print(f"  数据大小: {len(b''.join(frames))} 字节")
        print("\n✓ 测试完成")
        
    except Exception as e:
        print(f"✗ 测试失败: {e}")


def run_single_mode(mode_name: str, config_path: str, debug: bool = False):
    """
    直接运行单个模式（用于测试）
    
    Args:
        mode_name: 模式名称 (hand/pet/brightness)
        config_path: 配置文件路径
        debug: 调试模式
    """
    print("=" * 50)
    print(f"单模式运行: {mode_name}")
    print("=" * 50)
    
    # 模式映射
    mode_map = {
        'hand': ('smart_lamp.modes.hand_follow_mode', 'test_hand_follow_mode'),
        'pet': ('smart_lamp.modes.pet_mode', 'test_pet_mode'),
        'brightness': ('smart_lamp.modes.brightness_mode', 'test_brightness_mode'),
    }
    
    if mode_name not in mode_map:
        print(f"未知模式: {mode_name}")
        return 1
    
    module_name, test_func_name = mode_map[mode_name]
    
    try:
        import importlib
        module = importlib.import_module(module_name)
        test_func = getattr(module, test_func_name)
        test_func()
        return 0
    except Exception as e:
        print(f"运行失败: {e}")
        import traceback
        traceback.print_exc()
        return 1


def run_simulate():
    """模拟运行（不连接硬件）"""
    print("=" * 50)
    print("模拟模式 - 测试状态流转")
    print("=" * 50)
    
    from smart_lamp.core.main_controller import test_main_controller
    test_main_controller()


def main():
    """主函数"""
    args = parse_args()
    
    # 版本信息
    if args.version:
        show_version()
        return 0
    
    # 测试模式
    if args.test_servo:
        test_servo(args.config)
        return 0
    
    if args.test_camera:
        test_camera(args.config)
        return 0
    
    if args.test_voice:
        test_voice(args.config)
        return 0
    
    # 模拟模式
    if args.simulate:
        run_simulate()
        return 0
    
    # 单模式运行
    if args.mode:
        return run_single_mode(args.mode, args.config, args.debug)
    
    # ==================== 完整系统启动 ====================
    print("=" * 50)
    print("    智能台灯控制系统 v2.0")
    print("=" * 50)
    print()
    
    # 检查配置文件
    config_path = Path(args.config)
    if not config_path.exists():
        default_config = PROJECT_ROOT / 'config' / 'config.default.yaml'
        if default_config.exists():
            print(f"配置文件不存在，使用默认配置")
            args.config = str(default_config)
        else:
            print(f"错误: 配置文件不存在: {config_path}")
            return 1
    
    # 导入主控制器
    from smart_lamp.core.main_controller import MainController
    
    # 创建控制器
    controller = MainController(args.config)
    controller.debug = args.debug
    
    # 设置硬件模拟选项
    if args.no_servo:
        controller.simulate_servo = True
        print("📌 半模拟模式：舵机动作只打印不执行")
    
    if args.no_voice:
        controller.disable_voice = True
        print("📌 语音已禁用")
    
    # 设置信号处理
    def signal_handler(signum, frame):
        print("\n收到停止信号，正在关闭...")
        controller.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # 启动系统
    try:
        controller.start()
        
        # 主循环
        while controller.running:
            controller.update()
            
    except KeyboardInterrupt:
        print("\n用户中断")
    except Exception as e:
        print(f"\n运行时错误: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        controller.stop()
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
