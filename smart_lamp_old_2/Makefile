# ============================================
# 智能台灯 Makefile
# ============================================

.PHONY: help install run test clean update freeze service logs lint format

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

# Windows 兼容
ifeq ($(OS),Windows_NT)
	VENV := .venv
	PYTHON := $(VENV)/Scripts/python
	PIP := $(VENV)/Scripts/pip
endif

# 默认目标
help:
	@echo "智能台灯 - 可用命令:"
	@echo ""
	@echo "  make install     - 安装依赖"
	@echo "  make run         - 运行程序"
	@echo "  make run-debug   - 调试模式运行"
	@echo "  make test        - 运行测试"
	@echo "  make freeze      - 锁定依赖版本"
	@echo "  make update      - 更新依赖"
	@echo "  make clean       - 清理环境"
	@echo "  make service     - 安装系统服务"
	@echo "  make logs        - 查看服务日志"
	@echo ""

# 安装（完整）
install:
	bash scripts/install.sh

# 快速安装（跳过系统依赖）
install-quick:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements/requirements.txt
	@echo "安装完成！"

# 运行
run:
	$(PYTHON) run.py

# 调试模式
run-debug:
	$(PYTHON) run.py --debug

# 测试
test:
	$(PYTHON) -m pytest tests/ -v

# 测试覆盖率
test-cov:
	$(PYTHON) -m pytest tests/ -v --cov=smart_lamp --cov-report=html

# 锁定依赖
freeze:
	$(PIP) freeze > requirements/requirements.txt
	@echo "依赖已锁定到 requirements/requirements.txt"

# 更新依赖
update:
	$(PIP) install --upgrade -r requirements/requirements.txt
	$(PIP) freeze > requirements/requirements.txt
	@echo "依赖已更新"

# 清理
clean:
	rm -rf $(VENV)
	rm -rf __pycache__
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "清理完成"

# 安装系统服务
service:
	sudo cp systemd/smart-lamp.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable smart-lamp
	@echo "服务已安装"
	@echo "启动: sudo systemctl start smart-lamp"

# 查看日志
logs:
	journalctl -u smart-lamp -f

# 代码检查
lint:
	$(PYTHON) -m flake8 smart_lamp/ --max-line-length=100
	$(PYTHON) -m black --check smart_lamp/

# 代码格式化
format:
	$(PYTHON) -m black smart_lamp/
	$(PYTHON) -m isort smart_lamp/

# 复制舵机 SDK
copy-sdk:
	cp -r ../FTServo_Python/scservo_sdk smart_lamp/modules/servo/
	@echo "舵机 SDK 已复制"

# 创建配置文件
init-config:
	cp config/config.default.yaml config/config.yaml
	@echo "配置文件已创建，请编辑 config/config.yaml"
