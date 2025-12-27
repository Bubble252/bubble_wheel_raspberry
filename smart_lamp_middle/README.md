# 🏮 智能台灯控制系统 v2.0

> 基于树莓派的智能交互台灯，支持多种交互模式切换。

---

## ✨ 功能模式

### 🎯 三大模式

| 模式 | 功能 | 触发方式 |
|------|------|----------|
| **🖐️ 手部跟随** | 台灯跟随手部移动 | 说"手部跟随" |
| **🐱 桌宠模式** | 语音控制表情动作 | 说"桌宠模式" |
| **💡 亮度调节** | 手势控制灯光亮度 | 说"亮度调节" |

### 🔄 状态流转

```
┌─────────────────────────────────────────────────────┐
│                                                     │
│   STANDBY (待机)                                    │
│      │                                              │
│      └─── 说"宝莉" ───► LISTENING (监听)           │
│                              │                      │
│                              ├─ "手部跟随" ──► 🖐️  │
│                              ├─ "桌宠模式" ──► 🐱  │
│                              ├─ "亮度调节" ──► 💡  │
│                              │                      │
│                              └─ 10秒超时 ──► STANDBY│
│                                                     │
│   任意模式中:                                       │
│      ├─ 说"退出" ────────────► STANDBY             │
│      └─ 说"切换到XX" ────────► 其他模式            │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## 🚀 快速开始

### 1. 安装

```bash
# 克隆到树莓派
cd ~
git clone <your-repo> smart_lamp
cd smart_lamp

# 一键安装
bash scripts/install.sh

# 激活环境
source .venv/bin/activate

# 编辑配置（填入讯飞API）
cp config/config.default.yaml config/config.yaml
nano config/config.yaml
```

### 2. 运行

```bash
# 完整系统
python run.py

# 调试模式
python run.py --debug

# 直接进入某个模式（测试用）
python run.py --mode hand       # 手部跟随
python run.py --mode pet        # 桌宠模式
python run.py --mode brightness # 亮度调节

# 模拟模式（不连接硬件）
python run.py --simulate
```

### 3. 测试硬件

```bash
python run.py --test-camera  # 测试摄像头
python run.py --test-servo   # 测试舵机
python run.py --test-voice   # 测试麦克风
```

---

## 🎮 使用说明

### 基本流程

1. **唤醒台灯**
   ```
   你: "宝莉"
   台灯: [进入监听状态]
   终端: "请说模式名称：手部跟随、桌宠模式、亮度调节"
   ```

2. **选择模式**
   ```
   你: "桌宠模式"
   台灯: [进入桌宠模式，打招呼]
   ```

3. **模式内交互**
   - 手部跟随：移动手，台灯跟随
   - 桌宠模式：说"卖萌"、"跳舞"等
   - 亮度调节：张开/握拳手掌控制亮度

4. **退出/切换**
   ```
   你: "退出"        → 返回待机
   你: "切换到手部跟随" → 切换模式
   ```

### 🐱 桌宠模式命令

| 命令 | 动作 |
|------|------|
| 卖萌/可爱/撒娇 | 萌动作 |
| 跳舞/蹦迪 | 跳舞动作 |
| 点头 | 点头 |
| 摇头 | 摇头 |
| 打招呼/招手 | 挥手 |
| 睡觉/休息 | 休眠姿态 |
| 醒来/起来 | 唤醒动作 |
| 随便/随机 | 随机动作 |

### 💡 亮度调节手势

| 手势 | 亮度 |
|------|------|
| ✋ 张开手掌 | 100% 最亮 |
| 🤚 半握 | 50% 中等 |
| ✊ 握拳 | 0% 关灯 |

---

## 📁 项目结构

```
smart_lamp/
├── config/
│   ├── config.default.yaml  # 配置模板
│   └── actions.yaml         # 动作库
│
├── smart_lamp/
│   ├── core/                # 核心模块
│   │   ├── state_machine.py     # 状态机
│   │   └── main_controller.py   # 主控制器
│   │
│   ├── modes/               # 功能模式 ⭐
│   │   ├── base_mode.py         # 模式基类
│   │   ├── hand_follow_mode.py  # 手部跟随
│   │   ├── pet_mode.py          # 桌宠模式
│   │   └── brightness_mode.py   # 亮度调节
│   │
│   ├── modules/             # 硬件模块
│   │   ├── vision/              # 视觉
│   │   ├── voice/               # 语音
│   │   ├── servo/               # 舵机
│   │   └── lighting/            # 照明
│   │
│   └── utils/               # 工具
│
├── run.py                   # 入口文件
└── README.md
```

---

## 🔧 配置说明

### config/config.yaml

```yaml
# 唤醒词设置
wake_word: "宝莉"
listening_timeout: 10  # 监听超时(秒)

# 硬件配置
camera:
  index: 0
  width: 640
  height: 480

audio:
  device_index: null  # null=默认
  sample_rate: 16000

servo:
  port: "/dev/ttyUSB0"
  baudrate: 115200
  servo_ids: [1, 2, 3]

stm32:
  port: "/dev/ttyAMA0"
  baudrate: 115200

# 讯飞API (必填!)
xfyun:
  app_id: "你的APPID"
  api_key: "你的APIKEY"
  api_secret: "你的APISECRET"

# 模块开关
modules:
  camera:
    enabled: true
  voice:
    enabled: true
  servo:
    enabled: true
  lighting:
    enabled: true
```

---

## 🛠️ 开发指南

### 添加新模式

1. 创建模式文件 `smart_lamp/modes/my_mode.py`:

```python
from .base_mode import BaseMode

class MyMode(BaseMode):
    MODE_NAME = "我的模式"
    
    def on_enter(self):
        self._print("进入我的模式")
    
    def on_exit(self):
        self._print("退出我的模式")
    
    def update(self, frame=None, voice_text=None) -> bool:
        # 主循环逻辑
        return True  # 返回False退出模式
    
    def handle_voice(self, text: str) -> bool:
        # 处理语音命令
        if "某命令" in text:
            self._print("执行某操作")
            return True
        return False
```

2. 在 `state_machine.py` 中注册:

```python
class LampState(Enum):
    # ...
    MY_MODE = auto()

MODE_NAMES = {
    # ...
    LampState.MY_MODE: ['我的模式', '自定义模式'],
}
```

3. 在 `main_controller.py` 中添加:

```python
from ..modes.my_mode import MyMode

MODE_CLASSES = {
    # ...
    LampState.MY_MODE: MyMode,
}
```

### 单独测试模式

每个模式文件底部都有独立测试函数：

```bash
# 测试手部跟随
python -m smart_lamp.modes.hand_follow_mode

# 测试桌宠模式
python -m smart_lamp.modes.pet_mode

# 测试亮度调节
python -m smart_lamp.modes.brightness_mode
```

---

## 📊 终端输出示例

```
[14:30:15] ℹ ==================================================
[14:30:15] ℹ 智能台灯系统 - 初始化
[14:30:15] ℹ ==================================================
[14:30:15] ℹ 唤醒词: 宝莉
[14:30:15] ℹ 监听超时: 10.0秒
[14:30:15] ✓ 摄像头初始化成功
[14:30:15] ✓ 语音模块初始化成功
[14:30:16] ✓ 舵机模块初始化成功
[14:30:16] ✓ 系统启动完成
[14:30:16] ℹ --------------------------------------------------
[14:30:16] ℹ 说 "宝莉" 唤醒我
[14:30:16] ℹ --------------------------------------------------

[14:30:20] ✓ 唤醒词检测到: 宝莉
[14:30:20] 🎮 状态: STANDBY -> LISTENING
[14:30:20] ℹ 请说模式名称：手部跟随、桌宠模式、亮度调节

[14:30:23] 🎮 状态: LISTENING -> PET_MODE
[桌宠] 进入 [桌宠]
[桌宠] 我是你的桌宠！试试说：卖萌、跳舞、点头...

[14:30:28] [桌宠] 收到指令: 卖萌 -> 执行动作: cute
[Servo] 播放: cute

[14:30:35] [桌宠] 退出 [桌宠]，运行时长: 12.3秒
[14:30:35] 🎮 状态: PET_MODE -> STANDBY
[14:30:35] ℹ --------------------------------------------------
[14:30:35] ℹ 已返回待机，说 "宝莉" 唤醒
[14:30:35] ℹ --------------------------------------------------
```

---

## 🐛 故障排除

| 问题 | 解决方案 |
|------|----------|
| 摄像头打开失败 | `sudo usermod -a -G video $USER` 后重启 |
| 舵机无响应 | 检查 USB-TTL 连接，确认串口路径 |
| 语音无响应 | 检查麦克风，确认讯飞API配置 |
| MediaPipe安装失败 | `pip install --no-cache-dir mediapipe` |

---

## 📜 版本历史

### v2.0.0 (2024-12)
- ✨ 全新模式切换架构
- 🎮 三大交互模式
- 🗣️ 唤醒词+语音控制
- 🧪 支持单模式独立测试

### v1.0.0 (2024-12)
- 初始版本

---

**Made with ❤️ for Raspberry Pi**
