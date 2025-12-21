#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版语音识别 - 只识别"开机"和"关机"，不控制硬件
适用于测试语音识别功能或作为其他应用的基础
"""

import time
import base64
import hmac
import hashlib
import json
import websocket
import threading
import pyaudio
import datetime
import ssl
import urllib.parse

# ============================================
# 配置部分：填入你的科大讯飞开发者信息
# ============================================
APPID = "cac00df6"      # 你的APPID
APIKey = "b44a5920313b3b3302e918ba97e17450"    # 你的APIKey
APISecret = "NjJmMjdjMzMyNDFhYjY3YWM2NWI3NzZh"  # 你的APISecret

# 音频配置
SAMPLE_RATE = 48000  # 采样率：16000（推荐） 或 44100
# 16000Hz 适合语音识别，流量小，延迟低
# 44100Hz 音质更好但流量大，如需要改为 44100

# ============================================
# Websocket参数封装类
# ============================================
class Ws_Param(object):
    def __init__(self, APPID, APIKey, APISecret):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.host = "iat-api.xfyun.cn"
        self.request_uri = "/v2/iat"
        self.url = f"wss://{self.host}{self.request_uri}"

    def create_url(self):
        # 获取当前时间（GMT格式）
        now = datetime.datetime.utcnow()
        date = now.strftime('%a, %d %b %Y %H:%M:%S GMT')

        # 拼接签名原始字符串
        signature_origin = f"host: {self.host}\ndate: {date}\nGET {self.request_uri} HTTP/1.1"
        
        # HMAC-SHA256签名并base64编码
        signature_sha = hmac.new(
            self.APISecret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha_base64 = base64.b64encode(signature_sha).decode('utf-8')
        
        # 构造Authorization
        authorization_origin = (
            f'api_key="{self.APIKey}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature_sha_base64}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')

        # 构造URL参数
        params = {
            "authorization": authorization,
            "date": date,
            "host": self.host
        }
        url = self.url + '?' + urllib.parse.urlencode(params)
        return url


# ============================================
# 实时语音识别类
# ============================================
class SimpleVoiceRecognition:
    
    def __init__(self):
        self.ws_param = Ws_Param(APPID, APIKey, APISecret)
        self.url = self.ws_param.create_url()
        self.ws = None
        self.is_recording = True
        
        # 状态记录
        self.current_state = "关机"  # 初始状态
        
    def on_message(self, ws, message):
        """接收语音识别结果"""
        try:
            data = json.loads(message)
            
            # 检查是否有错误
            if data.get("code") != 0:
                print(f"❌ 识别出错: {data.get('message', '未知错误')}")
                return
            
            # 提取识别文本
            result = data["data"]["result"]["ws"]
            text = "".join([w["cw"][0]["w"] for w in result])
            
            if text:  # 只显示非空结果
                print(f"🎤 识别到: {text}")
                
                # 判断指令并执行相应操作
                # 支持多种表达方式和同音词
                turn_on_keywords = ["开机", "开启", "启动", "打开", "凯机"]
                turn_off_keywords = ["关机", "关闭", "停止", "光机"]
                
                # 检查是否包含开机关键词
                if any(keyword in text for keyword in turn_on_keywords):
                    self.turn_on()
                # 检查是否包含关机关键词
                elif any(keyword in text for keyword in turn_off_keywords):
                    self.turn_off()
                    
        except Exception as e:
            print(f"❌ 处理消息时出错: {e}")
    
    def turn_on(self):
        """开机操作"""
        if self.current_state == "开机":
            print("💡 系统已经是开机状态")
        else:
            self.current_state = "开机"
            print("✅ 开机成功！")
            print("=" * 50)
            # 这里可以添加你想要的其他操作
            # 例如：播放提示音、发送通知、记录日志等
    
    def turn_off(self):
        """关机操作"""
        if self.current_state == "关机":
            print("💡 系统已经是关机状态")
        else:
            self.current_state = "关机"
            print("✅ 关机成功！")
            print("=" * 50)
            # 这里可以添加你想要的其他操作

    def on_error(self, ws, error):
        """WebSocket错误处理"""
        print(f"❌ WebSocket错误: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        """WebSocket连接关闭"""
        print("\n🔌 WebSocket连接已关闭")
        if close_msg:
            print(f"   关闭原因: {close_msg}")
        
        # 如果不是主动退出，提示重新运行
        if self.is_recording:
            print("\n💡 提示：连接已断开，请重新运行程序")
            print("   或按 Ctrl+C 退出")

    def on_open(self, ws):
        """WebSocket连接建立后开始录音"""
        def run():
            try:
                # 初始化音频流
                p = pyaudio.PyAudio()
                
                # 根据采样率计算缓冲区大小（保持约50ms的音频）
                frames_per_buffer = int(SAMPLE_RATE * 0.05)  # 50ms
                
                stream = p.open(
                    format=pyaudio.paInt16,  # 16位采样
                    channels=1,              # 单声道
                    rate=SAMPLE_RATE,        # 采样率（16000 或 44100）
                    input=True,              # 输入模式
                    frames_per_buffer=frames_per_buffer  # 缓冲区大小
                )
                
                print("🎙️  开始录音... 请说\"开机\"或\"关机\"")
                print("=" * 50)
                print(f"当前状态: {self.current_state}")
                print("=" * 50)
                
                status = 0  # 0=首帧
                
                while self.is_recording:
                    # 读取音频数据
                    buf = stream.read(frames_per_buffer, exception_on_overflow=False)
                    if not buf:
                        continue
                    
                    # 构造数据包
                    data = {
                        "common": {"app_id": APPID},
                        "business": {
                            "language": "zh_cn",
                            "domain": "iat",
                            "accent": "mandarin",
                            "vad_eos": 600000  # 静音10分钟后自动断句
                        },
                        "data": {
                            "status": status,
                            "format": f"audio/L16;rate={SAMPLE_RATE}",  # 动态设置采样率
                            "audio": base64.b64encode(buf).decode(),
                            "encoding": "raw"
                        }
                    }
                    
                    # 发送数据
                    try:
                        ws.send(json.dumps(data))
                        status = 1  # 后续都是中间帧
                    except Exception as e:
                        print(f"\n⚠️  发送数据失败: {e}")
                        break
                    time.sleep(0.04)  # 40ms间隔
                
                # 发送结束标志
                try:
                    data = {
                        "data": {
                            "status": 2,  # 2=尾帧
                            "audio": "",
                            "format": f"audio/L16;rate={SAMPLE_RATE}",  # 动态设置采样率
                            "encoding": "raw"
                        }
                    }
                    ws.send(json.dumps(data))
                    time.sleep(1)
                except:
                    pass  # 连接已关闭，忽略
                
                # 清理资源
                stream.stop_stream()
                stream.close()
                p.terminate()
                
            except Exception as e:
                print(f"❌ 录音过程出错: {e}")
        
        # 在新线程中运行录音
        threading.Thread(target=run).start()

    def start(self):
        """启动语音识别"""
        print("=" * 50)
        print("🚀 简化版语音识别系统启动")
        print("=" * 50)
        print("功能: 识别\"开机\"和\"关机\"指令")
        print("按 Ctrl+C 退出程序")
        print("=" * 50)
        
        try:
            websocket.enableTrace(False)
            self.ws = websocket.WebSocketApp(
                self.url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            
            # 持续运行
            self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
            
        except KeyboardInterrupt:
            print("\n\n👋 程序已退出")
            self.is_recording = False


# ============================================
# 主程序入口
# ============================================
if __name__ == "__main__":
    # 检查是否配置了API信息
    if APPID == "your_appid_here":
        print("⚠️  警告: 请先配置科大讯飞的APPID、APIKey和APISecret")
        print("请编辑脚本，修改第12-14行的配置信息")
        exit(1)
    
    # 创建并启动语音识别
    recognizer = SimpleVoiceRecognition()
    recognizer.start()
