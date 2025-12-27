"""
扬声器控制线程
管理语音播放队列，支持TTS和音乐播放
自动检测并使用USB扬声器
"""
import os
import re
import time
import random
import threading
import subprocess
from queue import Queue, Empty
from pathlib import Path
from typing import Optional, List, Dict, Callable, Tuple

from .tts_engine import TTSEngine


class SpeakerThread(threading.Thread):
    """
    扬声器控制线程
    
    功能：
    - TTS语音合成和播放
    - 音乐文件播放
    - 循环播放（如跳舞时的音乐）
    - 定时播放（如点头时每1.5秒说一次）
    - 自动检测USB扬声器
    """
    
    def __init__(self, config: dict = None):
        """
        初始化扬声器线程
        
        Args:
            config: 配置字典
        """
        super().__init__(daemon=True, name="SpeakerThread")
        
        self.config = config or {}
        self._running = False
        
        # 检测音频设备
        self._audio_device = self._detect_usb_speaker()
        
        # TTS引擎
        cache_dir = self.config.get('cache_dir', 'cache/tts')
        voice = self.config.get('voice', 'zh-CN-XiaoxiaoNeural')
        self.tts = TTSEngine(cache_dir=cache_dir, voice=voice)
        
        # 音乐目录
        self.music_dir = Path(self.config.get('music_dir', 'MP3'))
        
        # 播放队列
        self._queue: Queue = Queue()
        
        # 当前播放状态
        self._current_process: Optional[subprocess.Popen] = None
        self._is_playing = False
        self._play_lock = threading.Lock()
        
        # 循环播放控制
        self._loop_mode = False
        self._loop_type = None  # 'music_random', 'tts_interval'
        self._loop_text = None  # 循环播放的文本
        self._loop_interval = 0  # 循环间隔
        self._loop_thread: Optional[threading.Thread] = None
        self._stop_loop_flag = False
        
        # 预合成常用语音
        self._preload_common_phrases()
    
    def _detect_usb_speaker(self) -> Optional[str]:
        """
        检测USB扬声器
        
        Returns:
            音频设备字符串（如 "hw:2,0"），未找到返回 None
        """
        try:
            # 执行 aplay -l 获取设备列表
            result = subprocess.run(
                ['aplay', '-l'],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            output = result.stdout
            self._print(f"音频设备列表:\n{output}")
            
            # 存储所有找到的 USB 设备
            usb_devices = []
            
            # 解析输出，寻找 USB 设备
            # 格式: card 0: M1066 [Yundea M1066], device 0: USB Audio [USB Audio]
            lines = output.split('\n')
            for line in lines:
                # 匹配 card 行
                card_match = re.search(r'card (\d+): (\S+) \[([^\]]+)\]', line)
                if card_match:
                    card = card_match.group(1)
                    short_name = card_match.group(2)
                    full_name = card_match.group(3)
                    
                    # 跳过 HDMI 设备
                    if 'hdmi' in full_name.lower() or 'vc4' in short_name.lower():
                        continue
                    
                    # 检查是否是 USB 音频设备
                    if 'USB' in line:
                        usb_devices.append({
                            'card': card,
                            'name': full_name,
                            'short_name': short_name,
                            'line': line
                        })
            
            if not usb_devices:
                self._print("未找到USB音频设备，使用默认设备")
                return None
            
            # 优先选择扬声器（排除麦克风）
            # 麦克风通常包含: Mic, AB13X, Input 等关键词
            mic_keywords = ['mic', 'ab13x', 'input', 'capture', 'record']
            speaker_keywords = ['m1066', 'speaker', 'output', 'headphone', 'yundea']
            
            # 先找明确是扬声器的
            for dev in usb_devices:
                name_lower = dev['name'].lower() + dev['short_name'].lower()
                if any(kw in name_lower for kw in speaker_keywords):
                    # 使用 plughw 而不是 hw，这样 ALSA 会自动转换音频格式
                    device_str = f"plughw:{dev['card']},0"
                    self._print(f"检测到USB扬声器: {dev['name']} ({device_str})")
                    return device_str
            
            # 再排除明确是麦克风的
            for dev in usb_devices:
                name_lower = dev['name'].lower() + dev['short_name'].lower()
                if not any(kw in name_lower for kw in mic_keywords):
                    device_str = f"plughw:{dev['card']},0"
                    self._print(f"使用USB音频设备: {dev['name']} ({device_str})")
                    return device_str
            
            # 如果都像麦克风，用第一个
            dev = usb_devices[0]
            device_str = f"plughw:{dev['card']},0"
            self._print(f"使用USB设备(可能是麦克风): {dev['name']} ({device_str})")
            return device_str
            
        except Exception as e:
            self._print(f"检测音频设备失败: {e}")
            return None
    
    def _preload_common_phrases(self):
        """预加载常用语音"""
        common_phrases = [
            "主人，我在",
            "切换到桌宠模式",
            "切换到手势跟随模式", 
            "切换到情绪识别模式",
            "切换到灯光模式",
            "牛逼",
            "好的",
            "收到",
        ]
        
        # 在后台线程中预合成
        def preload():
            for phrase in common_phrases:
                self.tts.synthesize(phrase)
        
        threading.Thread(target=preload, daemon=True).start()
    
    def run(self):
        """线程主循环"""
        self._print("扬声器线程启动")
        self._running = True
        
        while self._running:
            try:
                # 获取播放任务
                task = self._queue.get(timeout=0.1)
                self._handle_task(task)
            except Empty:
                pass
            except Exception as e:
                self._print(f"任务处理错误: {e}")
        
        # 清理
        self.stop_all()
        self._print("扬声器线程退出")
    
    def _handle_task(self, task: Dict):
        """处理播放任务"""
        task_type = task.get('type')
        
        if task_type == 'speak':
            # TTS播放
            text = task.get('text', '')
            if text:
                self._speak(text)
                
        elif task_type == 'play_file':
            # 播放指定文件
            file_path = task.get('file')
            if file_path:
                self._play_audio(file_path)
                
        elif task_type == 'play_music_random':
            # 随机播放音乐
            self._play_random_music()
            
        elif task_type == 'start_loop_music':
            # 开始循环随机音乐
            self._start_loop_music()
            
        elif task_type == 'start_loop_tts':
            # 开始定时TTS
            text = task.get('text', '')
            interval = task.get('interval', 1.5)
            self._start_loop_tts(text, interval)
            
        elif task_type == 'stop_loop':
            # 停止循环
            self._stop_loop()
            
        elif task_type == 'stop':
            # 停止当前播放
            self._stop_current()
    
    def _speak(self, text: str):
        """播放TTS语音"""
        self._print(f"正在合成: {text}")
        audio_file = self.tts.synthesize(text)
        if audio_file:
            self._print(f"合成成功: {audio_file}")
            self._play_audio(audio_file)
        else:
            self._print(f"TTS合成失败: {text}")
    
    def _play_audio(self, file_path: str, wait: bool = True):
        """
        播放音频文件
        
        Args:
            file_path: 音频文件路径
            wait: 是否等待播放完成
        """
        if not os.path.exists(file_path):
            self._print(f"文件不存在: {file_path}")
            return
        
        with self._play_lock:
            # 停止当前播放
            self._stop_current()
            
            self._is_playing = True
            
            # 根据文件格式选择播放器
            ext = os.path.splitext(file_path)[1].lower()
            
            try:
                if ext in ['.mp3']:
                    # 使用 mpg123 播放 MP3
                    # -q: 静默模式
                    # --no-control: 禁用终端控制
                    # -o alsa: 指定使用 ALSA 输出驱动（重要！）
                    # -a: 指定音频设备
                    cmd = ['mpg123', '-q', '--no-control', '-o', 'alsa']
                    if self._audio_device:
                        cmd.extend(['-a', self._audio_device])
                    cmd.append(file_path)
                    self._print(f"执行命令: {' '.join(cmd)}")
                    
                    self._current_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.DEVNULL  # 关闭标准输入
                    )
                elif ext in ['.wav']:
                    # 使用 aplay 播放 WAV
                    # aplay 使用 -D 指定设备
                    cmd = ['aplay']
                    if self._audio_device:
                        cmd.extend(['-D', self._audio_device])
                    cmd.append(file_path)
                    self._print(f"执行命令: {' '.join(cmd)}")
                    
                    self._current_process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        stdin=subprocess.DEVNULL
                    )
                else:
                    # 使用 ffplay 播放其他格式
                    # ffplay 不直接支持ALSA设备，但可以用环境变量
                    env = os.environ.copy()
                    if self._audio_device:
                        env['AUDIODEV'] = self._audio_device
                    
                    self._current_process = subprocess.Popen(
                        ['ffplay', '-nodisp', '-autoexit', '-loglevel', 'quiet', file_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        env=env
                    )
                
                if wait:
                    self._current_process.wait()
                    # 打印输出以便调试
                    stdout, stderr = self._current_process.communicate()
                    if stderr:
                        self._print(f"播放器stderr: {stderr.decode('utf-8', errors='ignore')}")
                    
            except FileNotFoundError as e:
                self._print(f"播放器未安装: {e}")
            except Exception as e:
                self._print(f"播放失败: {e}")
            finally:
                if wait:
                    self._is_playing = False
    
    def _stop_current(self):
        """停止当前播放"""
        if self._current_process:
            try:
                self._current_process.terminate()
                self._current_process.wait(timeout=1)
            except:
                try:
                    self._current_process.kill()
                except:
                    pass
            self._current_process = None
        self._is_playing = False
    
    def _get_music_files(self) -> List[str]:
        """获取音乐文件列表"""
        if not self.music_dir.exists():
            self._print(f"音乐目录不存在: {self.music_dir}")
            return []
        
        music_files = []
        for ext in ['*.mp3', '*.wav', '*.ogg', '*.flac']:
            music_files.extend(self.music_dir.glob(ext))
        
        return [str(f) for f in music_files]
    
    def _play_random_music(self):
        """随机播放一首音乐"""
        music_files = self._get_music_files()
        if not music_files:
            self._print("没有找到音乐文件")
            return
        
        music_file = random.choice(music_files)
        self._print(f"播放: {os.path.basename(music_file)}")
        self._play_audio(music_file)
    
    def _start_loop_music(self):
        """开始循环随机播放音乐"""
        # 确保先完全停止之前的循环
        self._stop_loop()
        
        self._loop_mode = True
        self._loop_type = 'music_random'
        self._stop_loop_flag = False  # 重置标志
        
        def loop_music():
            self._print("开始循环播放音乐")
            while not self._stop_loop_flag:
                music_files = self._get_music_files()
                if not music_files:
                    time.sleep(1)
                    continue
                
                music_file = random.choice(music_files)
                self._print(f"循环播放: {os.path.basename(music_file)}")
                
                # 使用 wait=False，手动等待并检查停止标志
                self._play_audio(music_file, wait=False)
                
                # 等待播放完成，同时检查停止标志
                while self._current_process and self._current_process.poll() is None:
                    if self._stop_loop_flag:
                        self._stop_current()
                        break
                    time.sleep(0.1)
                
                if self._stop_loop_flag:
                    break
                
                # 短暂间隔
                time.sleep(0.3)
            
            self._loop_mode = False
            self._print("音乐循环线程退出")
        
        self._loop_thread = threading.Thread(target=loop_music, daemon=True)
        self._loop_thread.start()
    
    def _start_loop_tts(self, text: str, interval: float):
        """开始定时TTS播放"""
        # 确保先完全停止之前的循环
        self._stop_loop()
        
        self._loop_mode = True
        self._loop_type = 'tts_interval'
        self._loop_text = text
        self._loop_interval = interval
        self._stop_loop_flag = False  # 重置标志
        
        # 预合成
        audio_file = self.tts.synthesize(text)
        
        def loop_tts():
            self._print(f"开始循环TTS: {text}")
            while not self._stop_loop_flag:
                if audio_file:
                    # 使用 wait=False，手动等待并检查停止标志
                    self._play_audio(audio_file, wait=False)
                    
                    # 等待播放完成，同时检查停止标志
                    while self._current_process and self._current_process.poll() is None:
                        if self._stop_loop_flag:
                            self._stop_current()
                            break
                        time.sleep(0.05)
                
                if self._stop_loop_flag:
                    break
                
                # 等待间隔，同时检查停止标志
                wait_time = 0
                while wait_time < self._loop_interval and not self._stop_loop_flag:
                    time.sleep(0.1)
                    wait_time += 0.1
            
            self._loop_mode = False
            self._print("TTS循环线程退出")
        
        self._loop_thread = threading.Thread(target=loop_tts, daemon=True)
        self._loop_thread.start()
    
    def _stop_loop(self):
        """停止循环播放"""
        # 先设置停止标志
        self._stop_loop_flag = True
        
        # 强制停止当前播放进程
        self._stop_current()
        
        # 等待循环线程退出
        if self._loop_thread is not None and self._loop_thread.is_alive():
            # 再次确保进程被杀死
            self._stop_current()
            self._loop_thread.join(timeout=3)
            
            # 如果还没退出，打印警告
            if self._loop_thread.is_alive():
                self._print("警告: 循环线程未能正常退出")
        
        self._loop_mode = False
        self._loop_thread = None
        self._print("循环播放已停止")
    
    # ==================== 外部接口 ====================
    
    def speak(self, text: str):
        """
        播放TTS语音
        
        Args:
            text: 要朗读的文本
        """
        self._queue.put({'type': 'speak', 'text': text})
    
    def play_file(self, file_path: str):
        """
        播放指定音频文件
        
        Args:
            file_path: 音频文件路径
        """
        self._queue.put({'type': 'play_file', 'file': file_path})
    
    def play_random_music(self):
        """随机播放一首音乐"""
        self._queue.put({'type': 'play_music_random'})
    
    def start_dance_music(self):
        """开始跳舞音乐（循环随机播放）"""
        self._queue.put({'type': 'start_loop_music'})
    
    def start_nod_voice(self, text: str = "牛逼", interval: float = 1.5):
        """
        开始点头语音（定时循环播放）
        
        Args:
            text: 要播放的文本
            interval: 播放间隔（秒）
        """
        self._queue.put({'type': 'start_loop_tts', 'text': text, 'interval': interval})
    
    def stop_loop(self):
        """停止循环播放（异步，通过队列）"""
        self._queue.put({'type': 'stop_loop'})
    
    def stop(self):
        """停止当前播放（异步，通过队列）"""
        self._queue.put({'type': 'stop'})
    
    def stop_immediately(self):
        """
        立即停止所有播放（同步，直接执行）
        用于切换动作或退出模式时确保音乐立即停止
        """
        self._stop_loop()
        self._stop_current()
    
    def stop_all(self):
        """停止所有播放并退出"""
        self._stop_loop()
        self._stop_current()
    
    def shutdown(self):
        """关闭线程"""
        self._running = False
        self.stop_all()
        if self.is_alive():
            self.join(timeout=3)
    
    @property
    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._is_playing
    
    @property
    def is_looping(self) -> bool:
        """是否在循环播放"""
        return self._loop_mode
    
    def _print(self, message: str):
        """格式化打印"""
        print(f"[Speaker] {message}")


# ==================== 便捷函数 ====================

# 全局实例
_speaker_instance: Optional[SpeakerThread] = None


def get_speaker() -> SpeakerThread:
    """获取全局扬声器实例"""
    global _speaker_instance
    if _speaker_instance is None or not _speaker_instance.is_alive():
        _speaker_instance = SpeakerThread()
        _speaker_instance.start()
    return _speaker_instance


def speak(text: str):
    """快速朗读文本"""
    get_speaker().speak(text)


def play_music():
    """快速播放随机音乐"""
    get_speaker().play_random_music()


# ==================== 测试 ====================
if __name__ == "__main__":
    print("=" * 50)
    print("扬声器模块测试")
    print("=" * 50)
    
    speaker = SpeakerThread()
    speaker.start()
    
    time.sleep(1)  # 等待初始化
    
    try:
        print("\n测试命令:")
        print("  1. 说 '主人，我在'")
        print("  2. 说 '切换到桌宠模式'")
        print("  3. 播放随机音乐")
        print("  4. 开始循环音乐（跳舞）")
        print("  5. 开始循环语音（点头说牛逼）")
        print("  6. 停止循环")
        print("  7. 停止播放")
        print("  s <text>. 自定义文本")
        print("  q. 退出")
        
        while True:
            cmd = input("\n请输入命令: ").strip()
            
            if cmd == 'q':
                break
            elif cmd == '1':
                speaker.speak("主人，我在")
            elif cmd == '2':
                speaker.speak("切换到桌宠模式")
            elif cmd == '3':
                speaker.play_random_music()
            elif cmd == '4':
                speaker.start_dance_music()
            elif cmd == '5':
                speaker.start_nod_voice("牛逼", 1.5)
            elif cmd == '6':
                speaker.stop_loop()
            elif cmd == '7':
                speaker.stop()
            elif cmd.startswith('s '):
                text = cmd[2:].strip()
                if text:
                    speaker.speak(text)
            else:
                print("未知命令")
            
    except KeyboardInterrupt:
        print("\n用户中断")
    finally:
        speaker.shutdown()
        print("测试结束")
