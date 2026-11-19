"""实时字幕翻译 Web 服务 - 手机端可用"""
import time
import random
import threading
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from deep_translator import GoogleTranslator, MyMemoryTranslator
import socket
import os

app = Flask(__name__, static_folder='web', static_url_path='')
CORS(app)

# 翻译器字典，按 src_key 缓存
_translators = {}
_lock = threading.Lock()

# 语言代码映射（key -> (MyMemory代码, Google代码)）
LANG_MAP = {
    'lebanon':     ('ar-SA', 'ar'),
    'philippines': ('fil-PH', 'tl'),
    'bangladesh':  ('bn-IN', 'bn'),
    'korea':       ('ko-KR', 'ko'),
    'english':     ('en-GB', 'en'),
}


def _get_translator(src_key: str, target: str = 'zh-CN'):
    with _lock:
        cache_key = f"{src_key}|{target}"
        if cache_key in _translators:
            return _translators[cache_key]

        mm_code, g_code = LANG_MAP.get(src_key, (src_key, src_key))

        class _ProxyTranslator:
            def __init__(self):
                self._mm = None
                self._gg = None
                self._backoff_until = {}
                self._min_interval = 0.5
                self._last_time = 0
                # 初始化后端
                try:
                    self._mm = MyMemoryTranslator(source=mm_code, target=target)
                except Exception:
                    pass
                try:
                    self._gg = GoogleTranslator(source=g_code, target=target)
                except Exception:
                    pass

            def translate(self, text):
                if not text or not text.strip():
                    return ""
                # 限流
                now = time.time()
                if now - self._last_time < self._min_interval:
                    time.sleep(self._min_interval - (now - self._last_time))
                self._last_time = time.time()

                for name, backend in [('MyMemory', self._mm), ('Google', self._gg)]:
                    if backend is None:
                        continue
                    if name in self._backoff_until and time.time() < self._backoff_until[name]:
                        continue
                    try:
                        r = backend.translate(text)
                        if r and r.strip():
                            return r.strip()
                    except Exception as e:
                        s = str(e).lower()
                        if 'too many' in s or '429' in s or 'limit' in s:
                            self._backoff_until[name] = time.time() + random.uniform(8, 20)
                return ""

        t = _ProxyTranslator()
        _translators[cache_key] = t
        return t


@app.route('/')
def index():
    return send_from_directory('web', 'index.html')


@app.route('/translate', methods=['POST'])
def translate():
    data = request.get_json(force=True, silent=True) or {}
    src = data.get('src', 'lebanon')
    target = data.get('target', 'zh-CN')
    text = data.get('text', '').strip()

    if not text:
        return jsonify({'ok': True, 'translation': ''})

    translator = _get_translator(src, target)
    result = translator.translate(text)
    return jsonify({'ok': True, 'translation': result})


def get_lan_ip():
    """获取本机局域网IP"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return '127.0.0.1'


if __name__ == '__main__':
    os.makedirs('web', exist_ok=True)
    port = 5001
    lan = get_lan_ip()
    print("=" * 50)
    print("实时字幕翻译 Web 服务")
    print(f"本机访问: http://localhost:{port}")
    print(f"手机访问: http://{lan}:{port}")
    print("=" * 50)
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
