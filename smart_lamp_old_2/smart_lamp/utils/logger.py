"""
日志模块
统一的日志管理
"""
import sys
import logging
from typing import Optional
from pathlib import Path


# 全局日志器缓存
_loggers = {}

# 日志格式
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logger(
    level: str = "INFO",
    log_file: Optional[str] = None,
    debug: bool = False
) -> logging.Logger:
    """
    设置全局日志配置
    
    Args:
        level: 日志级别 (DEBUG, INFO, WARNING, ERROR)
        log_file: 日志文件路径（可选）
        debug: 是否开启调试模式
    """
    if debug:
        level = "DEBUG"
    
    # 获取根日志器
    root_logger = logging.getLogger("smart_lamp")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    
    # 清除现有处理器
    root_logger.handlers.clear()
    
    # 控制台处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
    root_logger.addHandler(console_handler)
    
    # 文件处理器（可选）
    if log_file:
        try:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            file_handler.setFormatter(logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT))
            root_logger.addHandler(file_handler)
        except Exception as e:
            root_logger.warning(f"无法创建日志文件: {e}")
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    获取模块日志器
    
    Args:
        name: 模块名称
        
    Returns:
        日志器实例
    """
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(f"smart_lamp.{name}")
    _loggers[name] = logger
    return logger


class LoggerMixin:
    """
    日志混入类
    为类提供 self.logger 属性
    """
    
    @property
    def logger(self) -> logging.Logger:
        if not hasattr(self, '_logger'):
            self._logger = get_logger(self.__class__.__name__)
        return self._logger
