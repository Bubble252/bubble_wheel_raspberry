#!/usr/bin/env python3
"""测试 USB 扬声器自动检测"""

import sys
sys.path.insert(0, '.')

from smart_lamp.modules.speaker.speaker_thread import SpeakerThread

print("创建 SpeakerThread...")
speaker = SpeakerThread()

print(f"检测到的USB设备: {speaker._audio_device}")

# 测试检测函数
device = speaker._detect_usb_speaker()
print(f"_detect_usb_speaker() 返回: {device}")

# 测试播放（可选）
print("\n测试 TTS 播放...")
speaker.start()
speaker.speak("USB扬声器检测成功")

import time
time.sleep(3)

speaker.stop()
print("测试完成")
