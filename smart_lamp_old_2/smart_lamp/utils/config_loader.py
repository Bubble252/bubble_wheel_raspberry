"""
配置加载器
加载和管理 YAML 配置文件
"""
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
import copy


# 默认配置
DEFAULT_CONFIG = {
    'system': {
        'name': '智能台灯',
        'version': '1.0.0',
        'log_level': 'INFO'
    },
    'devices': {
        'camera': {
            'device_id': 0,
            'width': 640,
            'height': 480,
            'fps': 15
        },
        'microphone': {
            'device_index': None,
            'sample_rate': 16000,
            'chunk_size': 1024
        },
        'servo': {
            'port': '/dev/ttyUSB0',
            'baudrate': 1000000,
            'ids': [1, 2, 3]
        }
    },
    'stm32': {
        'port': '/dev/ttyAMA0',
        'baudrate': 115200,
        'timeout': 1
    },
    'modules': {
        'vision': {
            'enabled': True,
            'face_detection': True,
            'emotion_detection': True,
            'gesture_detection': True,
            'process_interval': 0.1
        },
        'voice': {
            'enabled': True,
            'api': 'xunfei',
            'app_id': '',
            'api_key': '',
            'api_secret': ''
        }
    },
    'defaults': {
        'brightness': 0.5,
        'idle_timeout': 30
    }
}


def deep_merge(base: Dict, override: Dict) -> Dict:
    """
    深度合并字典
    
    Args:
        base: 基础字典
        override: 覆盖字典
        
    Returns:
        合并后的字典
    """
    result = copy.deepcopy(base)
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    
    return result


def load_config(config_path: str = "config/config.yaml") -> Dict[str, Any]:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径
        
    Returns:
        配置字典
    """
    config = copy.deepcopy(DEFAULT_CONFIG)
    
    path = Path(config_path)
    
    # 如果指定配置不存在，尝试默认配置
    if not path.exists():
        default_path = Path("config/config.default.yaml")
        if default_path.exists():
            path = default_path
            print(f"使用默认配置: {default_path}")
        else:
            print("配置文件不存在，使用内置默认配置")
            return config
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            file_config = yaml.safe_load(f) or {}
        
        # 合并配置
        config = deep_merge(config, file_config)
        print(f"配置加载成功: {path}")
        
    except Exception as e:
        print(f"加载配置失败: {e}，使用默认配置")
    
    return config


def save_config(config: Dict[str, Any], config_path: str = "config/config.yaml"):
    """
    保存配置到文件
    
    Args:
        config: 配置字典
        config_path: 保存路径
    """
    path = Path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
        print(f"配置保存成功: {path}")
    except Exception as e:
        print(f"保存配置失败: {e}")


def get_nested(config: Dict, *keys, default=None):
    """
    获取嵌套配置值
    
    示例:
        get_nested(config, 'devices', 'camera', 'fps', default=15)
    """
    value = config
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
        else:
            return default
        if value is None:
            return default
    return value
