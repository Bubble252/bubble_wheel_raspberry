#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦克风检测工具 - 检测麦克风设备和支持的采样率
"""

import pyaudio

def check_microphone():
    """检测麦克风设备和支持的采样率"""
    
    print("=" * 70)
    print("🎤 麦克风检测工具")
    print("=" * 70)
    
    try:
        p = pyaudio.PyAudio()
        
        # 1. 列出所有音频设备
        print("\n📋 检测到的音频设备：")
        print("-" * 70)
        
        device_count = p.get_device_count()
        input_devices = []
        
        for i in range(device_count):
            info = p.get_device_info_by_index(i)
            
            # 只显示输入设备（麦克风）
            if info['maxInputChannels'] > 0:
                input_devices.append((i, info))
                print(f"\n设备 {i}: {info['name']}")
                print(f"  类型: 输入设备（麦克风）")
                print(f"  输入通道数: {info['maxInputChannels']}")
                print(f"  默认采样率: {int(info['defaultSampleRate'])} Hz")
        
        if not input_devices:
            print("\n❌ 未检测到麦克风设备！")
            p.terminate()
            return
        
        # 2. 获取默认输入设备
        print("\n" + "=" * 70)
        print("🎯 默认麦克风设备：")
        print("-" * 70)
        
        try:
            default_input_index = p.get_default_input_device_info()['index']
            default_info = p.get_device_info_by_index(default_input_index)
            print(f"设备 {default_input_index}: {default_info['name']}")
            print(f"默认采样率: {int(default_info['defaultSampleRate'])} Hz")
        except:
            print("⚠️  无法获取默认输入设备")
            default_input_index = input_devices[0][0]
            default_info = input_devices[0][1]
            print(f"使用第一个检测到的设备: {default_info['name']}")
        
        # 3. 测试常用采样率
        print("\n" + "=" * 70)
        print(f"🧪 测试设备 {default_input_index} 支持的采样率：")
        print("-" * 70)
        
        test_rates = [8000, 11025, 16000, 22050, 32000, 44100, 48000, 96000]
        supported_rates = []
        
        for rate in test_rates:
            try:
                # 尝试打开音频流
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=rate,
                    input=True,
                    input_device_index=default_input_index,
                    frames_per_buffer=1024
                )
                stream.close()
                supported_rates.append(rate)
                print(f"✅ {rate:6d} Hz - 支持")
            except Exception as e:
                print(f"❌ {rate:6d} Hz - 不支持")
        
        # 4. 推荐设置
        print("\n" + "=" * 70)
        print("💡 推荐设置：")
        print("-" * 70)
        
        if supported_rates:
            print(f"\n你的麦克风支持以下采样率：")
            print(f"  {', '.join([str(r) for r in supported_rates])} Hz")
            
            print(f"\n📌 推荐配置：")
            
            if 16000 in supported_rates:
                print(f"  SAMPLE_RATE = 16000  ⭐⭐⭐⭐⭐ 强烈推荐")
                print(f"    - 最适合语音识别")
                print(f"    - 网络流量小，延迟低")
                print(f"    - 识别准确率高")
            
            if 44100 in supported_rates:
                print(f"\n  SAMPLE_RATE = 44100  ⭐⭐⭐")
                print(f"    - CD音质")
                print(f"    - 音质好但流量大")
                print(f"    - 语音识别效果与16000相近")
            
            if 48000 in supported_rates:
                print(f"\n  SAMPLE_RATE = 48000  ⭐⭐⭐")
                print(f"    - 专业音频采样率")
                print(f"    - 适合高质量录音")
            
            # 默认采样率建议
            default_rate = int(default_info['defaultSampleRate'])
            print(f"\n📍 你的麦克风默认采样率: {default_rate} Hz")
            
            if default_rate == 44100:
                print(f"   建议改为 16000 Hz 以获得更好的语音识别性能")
            elif default_rate == 16000:
                print(f"   ✅ 非常适合语音识别！")
            else:
                print(f"   可以使用，但建议改为 16000 Hz")
        
        # 5. 配置示例
        print("\n" + "=" * 70)
        print("📝 在 voice_recognition_simple.py 中修改：")
        print("-" * 70)
        
        if 16000 in supported_rates:
            print("\nSAMPLE_RATE = 16000  # 推荐：最适合语音识别")
        elif 44100 in supported_rates:
            print("\nSAMPLE_RATE = 44100  # CD音质")
        elif supported_rates:
            print(f"\nSAMPLE_RATE = {supported_rates[0]}  # 你的麦克风支持")
        
        print("\n" + "=" * 70)
        
        p.terminate()
        
    except ImportError:
        print("\n❌ 错误：未安装 pyaudio")
        print("\n请先安装：")
        print("  Ubuntu: sudo apt install portaudio19-dev python3-dev")
        print("          pip3 install pyaudio")
        print("  Windows: pip install pyaudio")
    except Exception as e:
        print(f"\n❌ 检测过程出错: {e}")


if __name__ == "__main__":
    check_microphone()
