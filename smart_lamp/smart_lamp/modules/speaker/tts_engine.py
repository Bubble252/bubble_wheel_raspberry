"""
TTS语音合成引擎
支持多种TTS后端：pyttsx3（离线）、edge-tts（在线）
"""
import os
import time
import threading
import hashlib
from pathlib import Path
from typing import Optional


class TTSEngine:
    """
    TTS语音合成引擎
    
    功能：
    - 文本转语音
    - 支持缓存（避免重复合成）
    - 支持多种后端
    """
    
    def __init__(self, cache_dir: str = "cache/tts", voice: str = "zh-CN-XiaoxiaoNeural"):
        """
        初始化TTS引擎
        
        Args:
            cache_dir: 缓存目录
            voice: 语音名称（edge-tts使用）
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.voice = voice
        self._engine = None
        self._engine_type = None
        self._lock = threading.Lock()
        
        # 检测可用的TTS引擎
        self._detect_engine()
    
    def _detect_engine(self):
        """检测可用的TTS引擎"""
        # 优先使用 edge-tts（效果好）
        try:
            import edge_tts
            self._engine_type = "edge-tts"
            self._print("使用 edge-tts 引擎")
            return
        except ImportError:
            pass
        
        # 其次使用 pyttsx3（离线）
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._engine.setProperty('rate', 150)  # 语速
            self._engine_type = "pyttsx3"
            self._print("使用 pyttsx3 引擎")
            return
        except Exception as e:
            self._print(f"pyttsx3 初始化失败: {e}")
        
        # 最后使用 espeak（系统命令）
        if os.system("which espeak > /dev/null 2>&1") == 0:
            self._engine_type = "espeak"
            self._print("使用 espeak 引擎")
            return
        
        self._print("警告: 没有可用的TTS引擎！")
        self._engine_type = None
    
    def synthesize(self, text: str) -> Optional[str]:
        """
        合成语音
        
        Args:
            text: 要合成的文本
            
        Returns:
            音频文件路径，失败返回None
        """
        if not self._engine_type:
            return None
        
        # 计算缓存文件名
        text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
        cache_file = self.cache_dir / f"{text_hash}.mp3"
        
        # 如果缓存存在，直接返回
        if cache_file.exists():
            return str(cache_file)
        
        # 合成语音
        with self._lock:
            try:
                if self._engine_type == "edge-tts":
                    return self._synthesize_edge_tts(text, cache_file)
                elif self._engine_type == "pyttsx3":
                    return self._synthesize_pyttsx3(text, cache_file)
                elif self._engine_type == "espeak":
                    return self._synthesize_espeak(text, cache_file)
            except Exception as e:
                self._print(f"语音合成失败: {e}")
                return None
        
        return None
    
    def _synthesize_edge_tts(self, text: str, output_file: Path) -> Optional[str]:
        """使用 edge-tts 合成"""
        import asyncio
        import edge_tts
        
        async def _synthesize():
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(str(output_file))
        
        # 运行异步任务
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        loop.run_until_complete(_synthesize())
        
        if output_file.exists():
            return str(output_file)
        return None
    
    def _synthesize_pyttsx3(self, text: str, output_file: Path) -> Optional[str]:
        """使用 pyttsx3 合成"""
        # pyttsx3 保存为 wav
        wav_file = output_file.with_suffix('.wav')
        self._engine.save_to_file(text, str(wav_file))
        self._engine.runAndWait()
        
        if wav_file.exists():
            return str(wav_file)
        return None
    
    def _synthesize_espeak(self, text: str, output_file: Path) -> Optional[str]:
        """使用 espeak 合成"""
        wav_file = output_file.with_suffix('.wav')
        cmd = f'espeak -v zh "{text}" -w "{wav_file}"'
        os.system(cmd)
        
        if wav_file.exists():
            return str(wav_file)
        return None
    
    def speak_direct(self, text: str):
        """
        直接朗读文本（不保存文件）
        仅支持 pyttsx3 和 espeak
        """
        if self._engine_type == "pyttsx3":
            with self._lock:
                self._engine.say(text)
                self._engine.runAndWait()
        elif self._engine_type == "espeak":
            os.system(f'espeak -v zh "{text}"')
        else:
            # edge-tts 需要先合成再播放
            audio_file = self.synthesize(text)
            if audio_file:
                self._play_file(audio_file)
    
    def _play_file(self, file_path: str):
        """播放音频文件"""
        # 使用系统播放器
        if os.system("which mpg123 > /dev/null 2>&1") == 0:
            os.system(f'mpg123 -q "{file_path}"')
        elif os.system("which aplay > /dev/null 2>&1") == 0:
            os.system(f'aplay -q "{file_path}"')
        elif os.system("which ffplay > /dev/null 2>&1") == 0:
            os.system(f'ffplay -nodisp -autoexit -loglevel quiet "{file_path}"')
    
    def _print(self, message: str):
        """格式化打印"""
        print(f"[TTS] {message}")


# ==================== 测试 ====================
if __name__ == "__main__":
    print("=" * 50)
    print("TTS引擎测试")
    print("=" * 50)
    
    tts = TTSEngine()
    
    test_texts = [
        "主人，我在",
        "切换到桌宠模式",
        "牛逼",
    ]
    
    for text in test_texts:
        print(f"\n合成: {text}")
        audio_file = tts.synthesize(text)
        if audio_file:
            print(f"  -> {audio_file}")
        else:
            print("  -> 合成失败")
