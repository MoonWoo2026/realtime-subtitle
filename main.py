"""
实时字幕翻译 - MVP
支持黎巴嫩阿拉伯语 → 中文
"""
import sys
import os
import signal
import argparse

# macOS PyQt5 插件路径修复
try:
    import PyQt5
    _qt_plugins = os.path.join(os.path.dirname(PyQt5.__file__), 'Qt5', 'plugins', 'platforms')
    if os.path.isdir(_qt_plugins) and not os.environ.get('QT_QPA_PLATFORM_PLUGIN_PATH'):
        os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = _qt_plugins
except ImportError:
    pass

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import QTimer

from audio import AudioCapture
from asr import GoogleASR, TranscriberWorker
from translator import Translator
from overlay import SubtitleOverlay


class RealtimeSubtitleApp:
    def __init__(self, language='lebanon', device=None, debug=False):
        self.debug = debug

        # 初始化各模块
        self.asr = GoogleASR(language=language)
        self.translator = Translator(source=language, target='zh-CN')
        self.audio = AudioCapture(
            sample_rate=16000,
            block_duration=0.5,
            device=device,
            segment_duration=3.0,
        )
        self.worker = TranscriberWorker(self.asr, self.translator)
        self.worker.on_result = self._on_transcription_result

        # 音频回调 -> 送入处理队列
        self.audio.on_segment = self._on_audio_segment

    def _on_audio_segment(self, audio_data):
        """音频分段回调"""
        if self.debug:
            import numpy as np
            energy = np.max(np.abs(audio_data))
            if energy > 0.05:
                print(f"[Audio] segment len={len(audio_data)} energy={energy:.3f}")
        self.worker.submit(audio_data, self.audio.sample_rate)

    def _on_transcription_result(self, original: str, translated: str):
        """转录结果回调"""
        if self.debug:
            print(f"\n[Original]  {original}")
            print(f"[Translate] {translated}")
        # UI 更新通过信号
        if hasattr(self, 'overlay'):
            self.overlay.update_subtitle(original, translated)

    def start(self):
        """启动"""
        print("=" * 50)
        print("实时字幕翻译 MVP")
        print(f"识别语言: {self.asr.language_code}")
        print(f"翻译目标: {self.translator.target}")
        print(f"ASR后端: Google Speech Recognition")
        print(f"翻译后端: Google Translate")
        print("=" * 50)

        self.worker.start()
        self.audio.start()

    def stop(self):
        """停止"""
        self.audio.stop()
        self.worker.stop()

    def bind_overlay(self, overlay: SubtitleOverlay):
        """绑定UI，处理语言切换等"""
        self.overlay = overlay
        overlay.lang_combo.currentIndexChanged.connect(self._on_lang_change)
        overlay.toggle_btn.clicked.connect(self._on_toggle)

    def _on_lang_change(self):
        lang = self.overlay.get_selected_language()
        print(f"[App] 切换语言 -> {lang}")
        self.asr.set_language(lang)
        self.translator.set_source(lang)
        self.overlay.clear_subtitle()

    def _on_toggle(self):
        if self.overlay.is_running():
            self.audio.stop()
            self.overlay.set_running(False)
        else:
            self.audio.start()
            self.overlay.set_running(True)


def main():
    parser = argparse.ArgumentParser(description='实时字幕翻译')
    parser.add_argument('--lang', default='lebanon',
                        choices=['lebanon', 'philippines', 'bangladesh', 'korea', 'english'],
                        help='源语言 (默认: lebanon)')
    parser.add_argument('--device', type=int, default=None,
                        help='音频输入设备ID')
    parser.add_argument('--list-devices', action='store_true',
                        help='列出所有音频设备')
    parser.add_argument('--debug', action='store_true',
                        help='调试模式，打印更多日志')
    args = parser.parse_args()

    if args.list_devices:
        devices = AudioCapture.list_devices()
        print("\n可用音频输入设备:")
        print("-" * 50)
        for d in devices:
            if d['input']:
                print(f"  [{d['id']}] {d['name']}")
        print("-" * 50)
        print("使用 --device <ID> 指定输入设备")
        sys.exit(0)

    # 启动 Qt 应用
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 创建悬浮窗
    overlay = SubtitleOverlay()
    overlay.show()

    # 创建后端并绑定
    realtime_app = RealtimeSubtitleApp(
        language=args.lang,
        device=args.device,
        debug=args.debug,
    )
    realtime_app.bind_overlay(overlay)
    realtime_app.start()

    # 优雅退出
    def handle_signal(signum, frame):
        print("\n[App] 正在退出...")
        realtime_app.stop()
        app.quit()

    signal.signal(signal.SIGINT, handle_signal)

    # 托盘关闭事件
    app.aboutToQuit.connect(realtime_app.stop)

    # 启动事件循环
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
