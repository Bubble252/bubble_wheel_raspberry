#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音识别模块
直接照搬 voice_recognition_simple.py 的架构
"""

import time
import base64
import hmac
import hashlib
import json
import threading
import datetime
import ssl
import urllib.parse
from typing import Optional, Callable

try:
    import websocket
except ImportError:
    print("请安装 websocket-client: pip install websocket-client")
    websocket = None

try:
    import pyaudio
except ImportError:
    print("请安装 pyaudio: pip install pyaudio")
    pyaudio = None


# 固定配置
SAMPLE_RATE = 48000


class VoiceRecognizer:
    """
    语音识别器
    直接在 on_open 里启动录音线程，和原项目一样
    """
    
    def __init__(self, app_id: str, api_key: str, api_secret: str):
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        
        self.host = "iat-api.xfyun.cn"
        self.request_uri = "/v2/iat"
        
        self.ws = None
        self.is_running = False
        
        # 回调函数
        self._on_result: Optional[Callable[[str], None]] = None
        self._on_error: Optional[Callable[[str], None]] = None
        
    def _create_url(self) -> str:
        """创建带鉴权的 WebSocket URL"""
        now = datetime.datetime.utcnow()
        date = now.strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        signature_origin = f"host: {self.host}\ndate: {date}\nGET {self.request_uri} HTTP/1.1"
        
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha_base64 = base64.b64encode(signature_sha).decode('utf-8')
        
        authorization_origin = (
            f'api_key="{self.api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature_sha_base64}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        
        params = {
            "authorization": authorization,
            "date": date,
            "host": self.host
        }
        url = f"wss://{self.host}{self.request_uri}?" + urllib.parse.urlencode(params)
        return url
    
    def _on_message(self, ws, message):
        """接收语音识别结果"""
        try:
            data = json.loads(message)
            
            if data.get("code") != 0:
                error_msg = data.get("message", "未知错误")
                if self._on_error:
                    self._on_error(error_msg)
                return
            
            # 提取识别文本
            result = data["data"]["result"]["ws"]
            text = "".join([w["cw"][0]["w"] for w in result])
            
            if text and self._on_result:
                self._on_result(text)
                
        except Exception as e:
            if self._on_error:
                self._on_error(f"解析消息失败: {e}")
    
    def _on_error(self, ws, error):
        """WebSocket错误"""
        print(f"[Voice] WebSocket错误: {error}")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket关闭"""
        print("[Voice] 连接关闭")
    
    def _on_open(self, ws):
        """WebSocket连接成功后开始录音 - 这是关键！"""
        def recording_thread():
            try:
                p = pyaudio.PyAudio()
                
                # 50ms 的缓冲区
                frames_per_buffer = int(SAMPLE_RATE * 0.05)
                
                stream = p.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=SAMPLE_RATE,
                    input=True,
                    frames_per_buffer=frames_per_buffer
                )
                
                print("[Voice] 开始录音...")
                
                status = 0  # 0=首帧
                
                while self.is_running:
                    # 读取音频
                    buf = stream.read(frames_per_buffer, exception_on_overflow=False)
                    if not buf:
                        continue
                    
                    # 构造数据包 - 和原项目一样
                    data = {
                        "common": {"app_id": self.app_id},
                        "business": {
                            "language": "zh_cn",
                            "domain": "iat",
                            "accent": "mandarin",
                            "vad_eos": 600000  # 静音10分钟后自动断句
                        },
                        "data": {
                            "status": status,
                            "format": f"audio/L16;rate={SAMPLE_RATE}",
                            "audio": base64.b64encode(buf).decode(),
                            "encoding": "raw"
                        }
                    }
                    
                    # 发送
                    try:
                        ws.send(json.dumps(data))
                        status = 1  # 后续都是中间帧
                    except Exception as e:
                        print(f"[Voice] 发送失败: {e}")
                        break
                    
                    time.sleep(0.04)  # 40ms间隔
                
                # 清理
                stream.stop_stream()
                stream.close()
                p.terminate()
                
            except Exception as e:
                print(f"[Voice] 录音错误: {e}")
        
        # 启动录音线程
        threading.Thread(target=recording_thread, daemon=True).start()
    
    def start(self, on_result: Callable[[str], None], on_error: Callable[[str], None] = None):
        """
        启动语音识别
        
        Args:
            on_result: 识别结果回调
            on_error: 错误回调
        """
        if not websocket or not pyaudio:
            print("[Voice] 缺少依赖库")
            return False
        
        self._on_result = on_result
        self._on_error = on_error
        self.is_running = True
        
        url = self._create_url()
        
        self.ws = websocket.WebSocketApp(
            url,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # 在后台线程运行
        def run_ws():
            while self.is_running:
                try:
                    self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
                except Exception as e:
                    print(f"[Voice] WebSocket异常: {e}")
                
                if self.is_running:
                    print("[Voice] 断开，2秒后重连...")
                    time.sleep(2)
                    # 重新创建URL（因为有时间戳）
                    url = self._create_url()
                    self.ws = websocket.WebSocketApp(
                        url,
                        on_message=self._on_message,
                        on_error=self._on_error,
                        on_close=self._on_close,
                        on_open=self._on_open
                    )
        
        threading.Thread(target=run_ws, daemon=True).start()
        return True
    
    def stop(self):
        """停止语音识别"""
        self.is_running = False
        if self.ws:
            try:
                self.ws.close()
            except:
                pass


# 测试
if __name__ == "__main__":
    # 测试配置
    APP_ID = "cac00df6"
    API_KEY = "b44a5920313b3b3302e918ba97e17450"
    API_SECRET = "NjJmMjdjMzMyNDFhYjY3YWM2NWI3NzZh"
    
    def on_result(text):
        print(f"识别: {text}")
    
    def on_error(error):
        print(f"错误: {error}")
    
    recognizer = VoiceRecognizer(APP_ID, API_KEY, API_SECRET)
    recognizer.start(on_result, on_error)
    
    print("按 Ctrl+C 退出")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        recognizer.stop()
        print("退出")
