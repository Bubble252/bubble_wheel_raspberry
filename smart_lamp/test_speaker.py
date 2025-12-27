#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
扬声器模块测试
测试TTS语音合成和音乐播放功能
"""

import os
import sys
import time
from pathlib import Path

# 添加项目路径
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.insert(0, str(PROJECT_ROOT))

from smart_lamp.modules.speaker import SpeakerThread


def main():
    print("=" * 60)
    print("扬声器模块测试")
    print("=" * 60)
    
    # 检查MP3目录
    mp3_dir = PROJECT_ROOT / "MP3"
    if mp3_dir.exists():
        mp3_files = list(mp3_dir.glob("*.mp3"))
        print(f"MP3目录: {mp3_dir}")
        print(f"找到 {len(mp3_files)} 个MP3文件")
        for f in mp3_files[:5]:
            print(f"  - {f.name}")
        if len(mp3_files) > 5:
            print(f"  ... 还有 {len(mp3_files) - 5} 个")
    else:
        print(f"⚠ MP3目录不存在: {mp3_dir}")
        print("  请创建目录并放入MP3文件")
        mp3_dir.mkdir(exist_ok=True)
    
    print()
    
    # 启动扬声器线程
    config = {
        'cache_dir': 'cache/tts',
        'music_dir': 'MP3',
        'voice': 'zh-CN-XiaoxiaoNeural',
    }
    
    speaker = SpeakerThread(config)
    speaker.start()
    
    time.sleep(1)  # 等待初始化
    
    print("\n测试命令:")
    print("  1. 说 '主人，我在'")
    print("  2. 说 '切换到桌宠模式'")
    print("  3. 说 '牛逼'")
    print("  4. 播放随机音乐")
    print("  5. 开始循环音乐（跳舞模式）")
    print("  6. 开始循环语音（点头说牛逼，每1.5秒）")
    print("  7. 停止循环")
    print("  8. 停止当前播放")
    print("  s <文本>  自定义文本")
    print("  q  退出")
    print("-" * 60)
    
    try:
        while True:
            cmd = input("\n> ").strip()
            
            if not cmd:
                continue
            
            if cmd == 'q':
                break
            elif cmd == '1':
                speaker.speak("主人，我在")
            elif cmd == '2':
                speaker.speak("切换到桌宠模式")
            elif cmd == '3':
                speaker.speak("牛逼")
            elif cmd == '4':
                speaker.play_random_music()
            elif cmd == '5':
                speaker.start_dance_music()
                print("  开始循环音乐，输入 7 停止")
            elif cmd == '6':
                speaker.start_nod_voice("牛逼", 1.5)
                print("  开始循环语音，输入 7 停止")
            elif cmd == '7':
                speaker.stop_loop()
                print("  已停止循环")
            elif cmd == '8':
                speaker.stop()
                print("  已停止播放")
            elif cmd.startswith('s '):
                text = cmd[2:].strip()
                if text:
                    speaker.speak(text)
            else:
                print("  未知命令")
                
    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        speaker.shutdown()
        print("\n测试结束")


if __name__ == "__main__":
    main()
