"""
语音识别器
使用科大讯飞 WebSocket API
参考: voice_recognition/voice_recognition_simple.py
"""
import base64
import hmac
import hashlib
import json
import threading
import time
import datetime
import urllib.parse
from typing import Optional, Callable


class SpeechRecognizer:
    """
    语音识别器
    基于科大讯飞实时语音转写 API
    """
    
    # 固定采样率 48000Hz
    SAMPLE_RATE = 48000
    
    def __init__(self, app_id: str, api_key: str, api_secret: str):
        """
        初始化语音识别器
        
        Args:
            app_id: 讯飞 APPID
            api_key: 讯飞 APIKey
            api_secret: 讯飞 APISecret
        """
        self.app_id = app_id
        self.api_key = api_key
        self.api_secret = api_secret
        
        self.host = "iat-api.xfyun.cn"
        self.request_uri = "/v2/iat"
        
        self._ws = None
        self._on_result: Optional[Callable] = None
        self._on_error: Optional[Callable] = None
        self._connected = False
    
    def _create_url(self) -> str:
        """创建带鉴权的 WebSocket URL"""
        # 获取当前时间 (GMT格式)
        now = datetime.datetime.utcnow()
        date = now.strftime('%a, %d %b %Y %H:%M:%S GMT')
        
        # 拼接签名原始字符串
        signature_origin = f"host: {self.host}\ndate: {date}\nGET {self.request_uri} HTTP/1.1"
        
        # HMAC-SHA256 签名
        signature_sha = hmac.new(
            self.api_secret.encode('utf-8'),
            signature_origin.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        signature_sha_base64 = base64.b64encode(signature_sha).decode('utf-8')
        
        # 构造 Authorization
        authorization_origin = (
            f'api_key="{self.api_key}", '
            f'algorithm="hmac-sha256", '
            f'headers="host date request-line", '
            f'signature="{signature_sha_base64}"'
        )
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')
        
        # 构造 URL
        params = {
            "authorization": authorization,
            "date": date,
            "host": self.host
        }
        url = f"wss://{self.host}{self.request_uri}?" + urllib.parse.urlencode(params)
        return url
    
    def connect(self, on_result: Callable[[str], None], on_error: Callable[[str], None] = None, 
                on_close: Callable[[], None] = None):
        """
        连接到语音识别服务
        
        Args:
            on_result: 识别结果回调
            on_error: 错误回调
            on_close: 连接关闭回调
        """
        self._on_result = on_result
        self._on_error = on_error or (lambda e: print(f"语音识别错误: {e}"))
        self._on_close_callback = on_close
        
        # 重置状态
        self._connected = False
        self._first_frame_sent = False
        
        try:
            import websocket
            
            url = self._create_url()
            
            self._ws = websocket.WebSocketApp(
                url,
                on_message=self._on_message,
                on_error=self._on_ws_error,
                on_close=self._on_close,
                on_open=self._on_open
            )
            
            # 在后台线程运行
            thread = threading.Thread(
                target=lambda: self._ws.run_forever(sslopt={"cert_reqs": 0}),
                daemon=True
            )
            thread.start()
            
            # 等待连接
            timeout = 5
            start = time.time()
            while not self._connected and time.time() - start < timeout:
                time.sleep(0.1)
            
            return self._connected
            
        except ImportError:
            print("websocket-client 未安装")
            print("安装命令: pip install websocket-client")
            return False
        except Exception as e:
            print(f"连接失败: {e}")
            return False
    
    def send_audio(self, audio_data: bytes, is_last: bool = False):
        """
        发送音频数据
        
        Args:
            audio_data: PCM 音频数据
            is_last: 是否是最后一帧
        """
        if not self._ws or not self._connected:
            return
        
        # 构造请求数据
        status = 2 if is_last else 1  # 1=中间帧, 2=最后一帧
        
        # 第一帧需要包含公共参数和业务参数
        if not hasattr(self, '_first_frame_sent'):
            status = 0  # 0=第一帧
            self._first_frame_sent = True
        
        data = {
            "common": {"app_id": self.app_id} if status == 0 else None,
            "business": {
                "language": "zh_cn",
                "domain": "iat",
                "accent": "mandarin",
                "vad_eos": 6000000,  # 静音60000秒后才断句（最大值）
                "dwa": "wpgs"     # 动态修正
            } if status == 0 else None,
            "data": {
                "status": status,
                "format": f"audio/L16;rate={self.SAMPLE_RATE}",
                "encoding": "raw",
                "audio": base64.b64encode(audio_data).decode('utf-8')
            }
        }
        
        # 移除 None 值
        data = {k: v for k, v in data.items() if v is not None}
        
        try:
            self._ws.send(json.dumps(data))
        except Exception as e:
            print(f"发送音频失败: {e}")
    
    def _on_open(self, ws):
        """WebSocket 连接成功"""
        self._connected = True
        print("语音识别: 连接成功")
    
    def _on_message(self, ws, message):
        """收到消息"""
        try:
            data = json.loads(message)
            
            if data.get("code") != 0:
                error_msg = data.get("message", "未知错误")
                if self._on_error:
                    self._on_error(error_msg)
                return
            
            # 提取识别文本
            result = data.get("data", {}).get("result", {})
            ws_data = result.get("ws", [])
            
            text = ""
            for item in ws_data:
                for cw in item.get("cw", []):
                    text += cw.get("w", "")
            
            if text and self._on_result:
                self._on_result(text)
                
        except Exception as e:
            print(f"解析消息失败: {e}")
    
    def _on_ws_error(self, ws, error):
        """WebSocket 错误"""
        print(f"WebSocket 错误: {error}")
        if self._on_error:
            self._on_error(str(error))
    
    def _on_close(self, ws, close_status_code, close_msg):
        """WebSocket 关闭"""
        self._connected = False
        self._first_frame_sent = False
        print("语音识别: 连接关闭")
        # 调用关闭回调
        if hasattr(self, '_on_close_callback') and self._on_close_callback:
            self._on_close_callback()
    
    def disconnect(self):
        """断开连接"""
        self._connected = False
        if self._ws:
            try:
                self._ws.close()
            except:
                pass
            self._ws = None
    
    @property
    def is_connected(self) -> bool:
        """是否已连接"""
        return self._connected
