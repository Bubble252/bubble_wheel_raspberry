# 导入依赖
import time # 用于时间延迟
import base64 # 对音频数据和base64的编码
import hmac # HMAC加密
import hashlib # SHA256加密
import json # 序列化请求与解析返回json数据
import websocket # 建立Websocket连接
import threading # 创建音频录制线程 异步运行
import pyaudio # 麦克风音频采集
import datetime # 生成GMT时间格式
import ssl # websocket的ssl设置
import serial # 通过串口发送MODBUS指令控制继电器
import modbus_tk.defines as cst # 通过串口发送MODBUS指令控制继电器
import modbus_tk.modbus_rtu as modbus_rtu # 通过串口发送MODBUS指令控制继电器
import urllib.parse # URL参数编码

# 讯飞开发者信息
APPID = "xxx"
APIKey = "xxx"
APISecret = "xxx"

# 串口名称
PORT = "COM3"
# 设备地址
DEVICE_ADDR = 2

# --------------------------------------------
# 继电器连接函数
def ConnectRelay(port, slave_addr=2):
    try:
        #配置Modbus串口参数
        master = modbus_rtu.RtuMaster(serial.Serial(
            port=port,
            baudrate=9600,
            bytesize=8,
            parity='E',
            stopbits=1,
            timeout=2
        ))
        master.set_timeout(3.0) # 响应等待时间
        master.set_verbose(True) # 打印通信日志

        # 发送单个线圈指令测试是否连接成功
        print("正在测试继电器响应...")
        res = master.execute(slave_addr, cst.WRITE_SINGLE_COIL, 0, output_value=0)
        print(f"连接测试成功，返回值: {res}")
        return 1, master
    except Exception as exc:
        print("连接继电器失败:", str(exc))
        return -1, None

# 控制继电器开关
# 控制的是地址0的线圈（代表第一个继电器）
def Switch(master, action, slave_addr=2):
    try:
        if "on" in action.lower():
            res = master.execute(slave_addr, cst.WRITE_SINGLE_COIL, 0, output_value=1) # 若action是”on“，则发送写线圈值为1
            print("风扇已开启，返回：", res)
        else:
            res = master.execute(slave_addr, cst.WRITE_SINGLE_COIL, 0, output_value=0) # 若action是”off“，则写入0（关闭）
            print("风扇已关闭，返回：", res)
        return 1
    except Exception as exc:
        print("控制继电器失败:", str(exc))
        return -1

# --------------------------------------------
# Websocket参数封装类
class Ws_Param(object):
    def __init__(self, APPID, APIKey, APISecret):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.host = "iat-api.xfyun.cn" # 语音接口听写地址
        self.request_uri = "/v2/iat" # 接口路径
        self.url = f"wss://{self.host}{self.request_uri}" # websocket完整地址
        self.origin = f"https://{self.host}"

    def create_url(self):
        # 获取当前时间（GMT格式）
        now = datetime.datetime.utcnow()
        date = now.strftime('%a, %d %b %Y %H:%M:%S GMT')

        # 拼接签名原始字符串（host+date+请求行）
        signature_origin = f"host: {self.host}\ndate: {date}\nGET {self.request_uri} HTTP/1.1"
        # 用APISecret进行HMAC-SHA256签名，base64编码
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha_base64 = base64.b64encode(signature_sha).decode('utf-8')
        # 构造Authorization字符串，再次base64编码
        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode('utf-8')

        # 构造最终的Websocket URL
        params = {
            "authorization": authorization,
            "date": date,
            "host": self.host
        }
        url = self.url + '?' + urllib.parse.urlencode(params)
        return url


# --------------------------------------------
# 实时语音识别与控制
class RealTimeASR:

    def __init__(self, relay_master, slave_addr=2):
        self.relay_master = relay_master  # 继电器控制对象
        self.slave_addr = slave_addr #继电器地址
        self.ws_param = Ws_Param(APPID, APIKey, APISecret)
        self.url = self.ws_param.create_url() # 获取认证后的websocket地址
        self.ws = None # 定义是否正在录音的标志
        self.is_recording = True

    # 接收讯飞识别的结果
    def on_message(self, ws, message):
        data = json.loads(message)
        if data.get("code") != 0:
            print("识别出错:", data["message"])
            return
        result = data["data"]["result"]["ws"]
        # 拼接识别文本
        text = "".join([w["cw"][0]["w"] for w in result])
        print("识别结果：", text)
        # 拼接成字符串后判断是否包含”开风扇“或”关风扇“ 触发继电器的开或关
        if "开风扇" in text:
            Switch(self.relay_master, "on", self.slave_addr)
        elif "关风扇" in text:
            Switch(self.relay_master, "off", self.slave_addr)

    # 异常错误事件处理
    def on_error(self, ws, error):
        print("WebSocket 错误:", error)
    # 异常关闭事件处理
    def on_close(self, ws, close_status_code, close_msg):
        print("WebSocket 连接关闭")

    # websocket连接建立后的操作
    def on_open(self, ws):
        def run():
            #打开麦克风输入流
            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=800) #创建麦克风流 采样率16000Hz 单通道 16位
            print("开始录音... 说“开风扇”或“关风扇”")
            status = 0
            while self.is_recording:
                # 每800帧读取一次（0.04秒）
                buf = stream.read(800, exception_on_overflow=False)
                if not buf:
                    continue
                # 识别请求包
                data = {
                    "common": {"app_id": APPID},
                    "business": {"language": "zh_cn", "domain": "iat", "accent": "mandarin", "vad_eos": 10000},
                    "data": {"status": status, "format": "audio/L16;rate=16000", "audio": base64.b64encode(buf).decode(), "encoding": "raw"}
                }
                ws.send(json.dumps(data)) # 发送音频数据
                status = 1
                time.sleep(0.04) # 等待下个数据包

            # 结束标志
            data = {"data": {"status": 2, "audio": "", "format": "audio/L16;rate=16000", "encoding": "raw"}}
            ws.send(json.dumps(data))
            time.sleep(1)
            stream.stop_stream()
            stream.close()
            p.terminate()
        threading.Thread(target=run).start() # 创建新线程采集音频

    #启动函数 建立websocket连接 启动回调
    def start(self):
        websocket.enableTrace(False)
        self.ws = websocket.WebSocketApp(self.url,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close,
                                         on_open=self.on_open)
        # 持续运行websocket连接
        self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

# --------------------------------------------
if __name__ == "__main__":
    print("🔌 正在连接继电器模块...")
    code, master = ConnectRelay(PORT, DEVICE_ADDR)
    if code < 0:
        print("无法连接继电器模块，请检查串口或设备地址是否正确")
    else:
        print("连接成功，启动语音识别系统...")
        asr = RealTimeASR(master, DEVICE_ADDR) # 创建语音识别对象
        asr.start() # 启动识别
