#!/bin/bash
# ============================================
# 智能台灯 - 一键安装脚本
# 适用于树莓派 (Raspberry Pi OS)
# ============================================

set -e  # 出错即停

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}"
echo "========================================"
echo "   智能台灯 - 一键安装脚本"
echo "========================================"
echo -e "${NC}"

# 项目路径
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"

# ========================================
# 1. 检查 Python 版本
# ========================================
check_python() {
    echo -e "${YELLOW}[1/6] 检查 Python 版本...${NC}"
    
    if command -v python3.10 &> /dev/null; then
        PYTHON_CMD=python3.10
    elif command -v python3.11 &> /dev/null; then
        PYTHON_CMD=python3.11
    elif command -v python3 &> /dev/null; then
        PYTHON_CMD=python3
    else
        echo -e "${RED}错误: 未找到 Python3，请先安装${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}  使用: $($PYTHON_CMD --version)${NC}"
}

# ========================================
# 2. 安装系统依赖
# ========================================
install_system_deps() {
    echo -e "${YELLOW}[2/6] 安装系统依赖...${NC}"
    
    if [[ -f /etc/debian_version ]]; then
        sudo apt-get update
        sudo apt-get install -y \
            python3-dev \
            python3-venv \
            python3-pip \
            portaudio19-dev \
            libatlas-base-dev \
            libjpeg-dev \
            libopenjp2-7 \
            libtiff5 \
            libhdf5-dev
        echo -e "${GREEN}  系统依赖安装完成${NC}"
    else
        echo -e "${YELLOW}  非 Debian 系统，跳过 apt 安装${NC}"
    fi
}

# ========================================
# 3. 创建虚拟环境
# ========================================
create_venv() {
    echo -e "${YELLOW}[3/6] 创建虚拟环境...${NC}"
    
    if [[ -d "$VENV_DIR" ]]; then
        echo -e "${YELLOW}  虚拟环境已存在，跳过创建${NC}"
    else
        $PYTHON_CMD -m venv "$VENV_DIR"
        echo -e "${GREEN}  虚拟环境创建成功: $VENV_DIR${NC}"
    fi
    
    # 激活环境
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip wheel setuptools
}

# ========================================
# 4. 安装 Python 依赖
# ========================================
install_python_deps() {
    echo -e "${YELLOW}[4/6] 安装 Python 依赖...${NC}"
    
    source "$VENV_DIR/bin/activate"
    
    # 安装依赖
    if [[ -f "$PROJECT_DIR/requirements/requirements.txt" ]]; then
        pip install -r "$PROJECT_DIR/requirements/requirements.txt"
    else
        pip install numpy opencv-python-headless pyserial pyyaml
        pip install pyaudio websocket-client
        pip install mediapipe || echo "MediaPipe 安装失败，手势检测不可用"
        pip install fer || echo "FER 安装失败，情绪检测使用简化版"
    fi
    
    echo -e "${GREEN}  Python 依赖安装完成${NC}"
}

# ========================================
# 5. 复制舵机 SDK
# ========================================
copy_servo_sdk() {
    echo -e "${YELLOW}[5/6] 复制舵机 SDK...${NC}"
    
    SDK_SRC="$PROJECT_DIR/../FTServo_Python/scservo_sdk"
    SDK_DST="$PROJECT_DIR/smart_lamp/modules/servo/scservo_sdk"
    
    if [[ -d "$SDK_SRC" ]] && [[ ! -d "$SDK_DST" ]]; then
        cp -r "$SDK_SRC" "$SDK_DST"
        echo -e "${GREEN}  舵机 SDK 复制成功${NC}"
    elif [[ -d "$SDK_DST" ]]; then
        echo -e "${YELLOW}  舵机 SDK 已存在${NC}"
    else
        echo -e "${YELLOW}  未找到舵机 SDK，请手动复制${NC}"
    fi
}

# ========================================
# 6. 初始化配置
# ========================================
init_config() {
    echo -e "${YELLOW}[6/6] 初始化配置...${NC}"
    
    CONFIG_FILE="$PROJECT_DIR/config/config.yaml"
    DEFAULT_CONFIG="$PROJECT_DIR/config/config.default.yaml"
    
    if [[ ! -f "$CONFIG_FILE" ]] && [[ -f "$DEFAULT_CONFIG" ]]; then
        cp "$DEFAULT_CONFIG" "$CONFIG_FILE"
        echo -e "${GREEN}  配置文件已创建: $CONFIG_FILE${NC}"
        echo -e "${YELLOW}  请编辑配置文件填入你的讯飞 API 密钥${NC}"
    else
        echo -e "${YELLOW}  配置文件已存在${NC}"
    fi
}

# ========================================
# 7. 安装系统服务（可选）
# ========================================
install_service() {
    echo ""
    read -p "是否安装为开机自启服务? [y/N] " -n 1 -r
    echo
    
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        sudo cp "$PROJECT_DIR/systemd/smart-lamp.service" /etc/systemd/system/
        sudo systemctl daemon-reload
        sudo systemctl enable smart-lamp
        echo -e "${GREEN}  服务安装成功${NC}"
        echo "  启动服务: sudo systemctl start smart-lamp"
        echo "  查看日志: journalctl -u smart-lamp -f"
    fi
}

# ========================================
# 主流程
# ========================================
main() {
    check_python
    install_system_deps
    create_venv
    install_python_deps
    copy_servo_sdk
    init_config
    install_service
    
    echo ""
    echo -e "${GREEN}========================================"
    echo "   安装完成！"
    echo "========================================"
    echo ""
    echo "使用方法:"
    echo "  1. 激活环境: source $VENV_DIR/bin/activate"
    echo "  2. 编辑配置: nano config/config.yaml"
    echo "  3. 运行程序: python run.py"
    echo "  4. 或使用:   make run"
    echo -e "========================================${NC}"
}

main "$@"
