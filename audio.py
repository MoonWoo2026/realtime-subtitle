"""音频捕获模块 - 支持麦克风和系统音频"""
import sounddevice as sd
import numpy as np
import threading
import time


class AudioCapture:
    """实时音频捕获，分段回调"""

    def __init__(self, sample_rate=16000, channels=1, block_duration=0.5,
                 segment_duration=3.0, device=None):
        self.sample_rate = sample_rate
        self.channels = channels
        self.block_duration = block_duration  # 每次回调的音频时长(秒)
        self.segment_duration = segment_duration  # 每次送入ASR的音频段时长（秒）
        self.device = device

        self._stream = None
        self._running = False
        self._audio_buffer = []  # 积攒音频块，攒够一段再送ASR
        self._buffer_lock = threading.Lock()

        self._segment_blocks = int(self.segment_duration / self.block_duration)

        self.on_segment = None  # callback: f(audio_data: np.ndarray)

    @staticmethod
    def list_devices():
        """列出所有音频设备"""
        devices = sd.query_devices()
        result = []
        for i, dev in enumerate(devices):
            result.append({
                'id': i,
                'name': dev['name'],
                'input': dev['max_input_channels'] > 0,
                'output': dev['max_output_channels'] > 0,
                'default_sr': dev['default_samplerate'],
            })
        return result

    def start(self):
        """开始捕获"""
        if self._running:
            return

        block_size = int(self.sample_rate * self.block_duration)

        def callback(indata, frames, time_info, status):
            if status:
                print(f"[Audio] status: {status}")
            # 转为单声道 float32
            audio = indata.copy()
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            audio = audio.astype(np.float32)

            with self._buffer_lock:
                self._audio_buffer.append(audio)

            # 攒够一段就触发回调
            with self._buffer_lock:
                if len(self._audio_buffer) >= self._segment_blocks:
                    segment = np.concatenate(self._audio_buffer)
                    self._audio_buffer.clear()

            if self.on_segment and len(segment) > 0:
                self.on_segment(segment)

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=block_size,
            channels=self.channels,
            device=self.device,
            callback=callback,
            dtype='float32',
        )
        self._stream.start()
        self._running = True
        print(f"[Audio] 开始捕获, device={self.device}, "
              f"sr={self.sample_rate}, segment={self.segment_duration}s")

    def stop(self):
        """停止捕获"""
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._running = False
        print("[Audio] 停止捕获")

    def set_segment_duration(self, seconds):
        """调整分段时长"""
        self.segment_duration = max(1.0, min(10.0, seconds))
        self._segment_blocks = int(self.segment_duration / self.block_duration)
