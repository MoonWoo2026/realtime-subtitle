"""语音识别模块 - 支持多种ASR后端"""
import io
import threading
import numpy as np


class GoogleASR:
    """Google Speech Recognition API (免费版，无需API Key)"""

    # 语言代码映射
    LANG_MAP = {
        'lebanon': 'ar-LB',      # 黎巴嫩阿拉伯语
        'egypt': 'ar-EG',        # 埃及阿拉伯语
        'syria': 'ar-SY',        # 叙利亚阿拉伯语
        'philippines': 'fil-PH',  # 菲律宾语(他加禄语)
        'bangladesh': 'bn-BD',   # 孟加拉语
        'korea': 'ko-KR',        # 韩语
        'english': 'en-US',
    }

    def __init__(self, language='lebanon'):
        import speech_recognition as sr
        self._sr = sr
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 300
        self.recognizer.dynamic_energy_threshold = True
        self.set_language(language)

        # 降噪参数
        self.recognizer.pause_threshold = 0.8
        self.recognizer.phrase_threshold = 0.3

        print(f"[ASR] Google Speech Recognition 初始化, language={self.language_code}")

    def set_language(self, language):
        """设置识别语言"""
        lang_code = self.LANG_MAP.get(language, language)
        self.language = language
        self.language_code = lang_code

    def recognize(self, audio_data: np.ndarray, sample_rate=16000) -> str:
        """
        识别音频片段
        :param audio_data: float32 numpy array, 单声道
        :param sample_rate: 采样率
        :return: 识别文本，失败返回空字符串
        """
        try:
            # 检查音频能量，静音则跳过
            if np.max(np.abs(audio_data)) < 0.01:
                return ""

            # float32 -> int16 for speech_recognition
            audio_int16 = (audio_data * 32767).astype(np.int16)

            # 构造 AudioData 对象
            audio = self._sr.AudioData(
                audio_int16.tobytes(),
                sample_rate=sample_rate,
                sample_width=2  # int16 = 2 bytes
            )

            text = self.recognizer.recognize_google(
                audio,
                language=self.language_code,
                show_all=False
            )
            return text.strip()

        except self._sr.UnknownValueError:
            return ""
        except self._sr.RequestError as e:
            print(f"[ASR] Google API 错误: {e}")
            return ""
        except Exception as e:
            print(f"[ASR] 识别异常: {e}")
            return ""


class TranscriberWorker(threading.Thread):
    """异步转录工作线程"""

    def __init__(self, asr: GoogleASR, translator=None):
        super().__init__(daemon=True)
        self.asr = asr
        self.translator = translator
        self._queue = []
        self._queue_lock = threading.Lock()
        self._event = threading.Event()
        self._running = True

        self.on_result = None  # callback: f(original, translated)

    def submit(self, audio_data: np.ndarray, sample_rate=16000):
        """提交一段音频进行转录"""
        with self._queue_lock:
            self._queue.append((audio_data.copy(), sample_rate))
        self._event.set()

    def run(self):
        while self._running:
            self._event.wait(timeout=0.5)
            self._event.clear()

            # 取出一段音频（队列太长则丢弃旧的）
            with self._queue_lock:
                if len(self._queue) > 3:
                    # 丢弃前面积压的，只保留最新的
                    self._queue = self._queue[-1:]
                if not self._queue:
                    continue
                audio, sr = self._queue.pop(0)

            # 转录
            original = self.asr.recognize(audio, sr)

            if original and self.on_result:
                translated = ""
                if self.translator:
                    translated = self.translator.translate_with_retry(original, max_retries=1)
                self.on_result(original, translated)

    def stop(self):
        self._running = False
        self._event.set()
