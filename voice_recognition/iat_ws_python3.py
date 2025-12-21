##科大讯飞流式听写技术文档demo文件（python环境）
#导入依赖
import websocket #用于建立Websocket连接
import datetime
import hashlib #用于生成授权签名1
import base64 #用于生成授权签名2
import hmac #用于生成授权签名3
import json #处理数据的序列化与反序列化
from urllib.parse import urlencode #将鉴权参数转为URL查询字符串
import time
import ssl #处理加密连接
from wsgiref.handlers import format_date_time
from datetime import datetime
from time import mktime
import _thread as thread #多线程处理音频发送

#用于标记音频数据帧的状态
STATUS_FIRST_FRAME = 0  # 第一帧的标识 表示音频未在发送
STATUS_CONTINUE_FRAME = 1  # 中间帧标识 表示只发送音频数据
STATUS_LAST_FRAME = 2  # 最后一帧的标识 表示音频发送完毕

#这是构造Websocket连接和请求参数的核心类
class Ws_Param(object):
    # 构造方法用于初始化以下参数
    def __init__(self, APPID, APIKey, APISecret, AudioFile):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.AudioFile = AudioFile
        # 公共参数(common)
        self.CommonArgs = {"app_id": self.APPID}
        # 业务参数(business) 业务配置项 常见包括语种、口音、静音断句超时时间
        self.BusinessArgs = {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo":1,"vad_eos":10000}

    # 用于生成带签名的websocket请求URL
    def create_url(self):
        # 识别接口的websocket入口
        url = 'wss://ws-api.xfyun.cn/v2/iat'
        # 获取当前时间并格式化为RFC1123(HTTP标准时间格式）
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        # 构造签名原始字符串 按照讯飞要求为：host+date+请求行
        signature_origin = "host: " + "ws-api.xfyun.cn" + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + "/v2/iat " + "HTTP/1.1"
        # 用APISecret对前面原始字符串进行hmac-sha256加密 再base64编码
        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                                 digestmod=hashlib.sha256).digest()
        signature_sha = base64.b64encode(signature_sha).decode(encoding='utf-8')
        #构造并编码Authorization鉴权字段
        authorization_origin = "api_key=\"%s\", algorithm=\"%s\", headers=\"%s\", signature=\"%s\"" % (
            self.APIKey, "hmac-sha256", "host date request-line", signature_sha)
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')
        # 拼接为字典
        v = {
            "authorization": authorization,
            "date": date,
            "host": "ws-api.xfyun.cn"
        }
        # 最终生成带签名的Websocket URL
        url = url + '?' + urlencode(v)

        return url


# message是字符串类型的json，需解析 以下对收到讯飞返回的数据进行处理
def on_message(ws, message):
    try:
        code = json.loads(message)["code"]
        sid = json.loads(message)["sid"]
        if code != 0: # code表示状态码 0为解析成功 非0为错误
            errMsg = json.loads(message)["message"]
            print("sid:%s call error:%s code is:%s" % (sid, errMsg, code)) # sid是本次请求的会话ID

        else:
            data = json.loads(message)["data"]["result"]["ws"] #识别结果格式为嵌套结构
            result = ""
            for i in data: # 拼接识别到的文字
                for w in i["cw"]:
                    result += w["w"]
            print("sid:%s call success!,data is:%s" % (sid, json.dumps(data, ensure_ascii=False)))
    except Exception as e:
        print("receive msg,but parse exception:", e)


# 收到websocket错误的处理
def on_error(ws, error):
    print("### error:", error)


# 收到websocket关闭的处理
def on_close(ws,a,b):
    print("### closed ###")


# 收到websocket连接建立的处理
def on_open(ws):
    def run(*args): #建立连接后立即执行 使用子线程发送音频数据
        frameSize = 8000  # 每一帧的音频大小为8000字节 对应16k采样率
        intervel = 0.04  # 发送音频间隔为40ms
        status = STATUS_FIRST_FRAME  # 音频的状态信息 标识音频是第一帧、还是中间帧、最后一帧

        with open(wsParam.AudioFile, "rb") as fp: #以二进制形式读取音频
            while True:
                buf = fp.read(frameSize)
                # 文件结束
                if not buf:
                    status = STATUS_LAST_FRAME
                # 第一帧处理
                # 发送第一帧音频，带business 参数
                # appid 必须带上，只需第一帧发送
                if status == STATUS_FIRST_FRAME:
                    d = {"common": wsParam.CommonArgs,
                         "business": wsParam.BusinessArgs,
                         "data": {"status": 0, "format": "audio/L16;rate=16000",
                                  "audio": str(base64.b64encode(buf), 'utf-8'),
                                  "encoding": "raw"}}
                    d = json.dumps(d)
                    ws.send(d)
                    status = STATUS_CONTINUE_FRAME
                # 中间帧处理
                elif status == STATUS_CONTINUE_FRAME:
                    d = {"data": {"status": 1, "format": "audio/L16;rate=16000",
                                  "audio": str(base64.b64encode(buf), 'utf-8'),
                                  "encoding": "raw"}}
                    ws.send(json.dumps(d))
                # 最后一帧处理
                elif status == STATUS_LAST_FRAME:
                    d = {"data": {"status": 2, "format": "audio/L16;rate=16000",
                                  "audio": str(base64.b64encode(buf), 'utf-8'),
                                  "encoding": "raw"}}
                    ws.send(json.dumps(d))
                    time.sleep(1)
                    break
                # 模拟音频采样间隔
                time.sleep(intervel)
        ws.close()

    thread.start_new_thread(run, ())


if __name__ == "__main__":
    time1 = datetime.now()
    # 在下方填写自己账号殴打参数和音频路径
    wsParam = Ws_Param(APPID='xxx', APISecret='xxx',
                       APIKey='xxx',
                       AudioFile='D:/Zhinengxitong/iat_pcm_16k.pcm')
    websocket.enableTrace(False)
    # 生成Websocket URL
    wsUrl = wsParam.create_url()
    ws = websocket.WebSocketApp(wsUrl, on_message=on_message, on_error=on_error, on_close=on_close)
    ws.on_open = on_open
    ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
    time2 = datetime.now()
    print(time2-time1)

#另外补充：将语音识别结果文本化输出
import json

data = '[{"bg": 41, "cw": [{"sc": 0, "w": "语音"}]}, {"cw": [{"sc": 0, "w": "听写"}], "bg": 89}, {"bg": 185, "cw": [{"sc": 0, "w": "可以"}]}, {"bg": 233, "cw": [{"sc": 0, "w": "将"}]}, {"cw": [{"w": "语音", "sc": 0}], "bg": 257}, {"bg": 305, "cw": [{"sc": 0, "w": "转为"}]}, {"cw": [{"sc": 0, "w": "文字"}], "bg": 353}, {"cw": [{"sc": 0, "w": "。"}], "bg": 420}]'

# 解析 JSON
text_result = "".join([word["cw"][0]["w"] for word in json.loads(data)])
print("最终识别文本：", text_result)
