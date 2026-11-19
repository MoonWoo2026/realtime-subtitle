"""翻译模块 - 多后端带重试和退避"""
import time
import random
from deep_translator import GoogleTranslator, MyMemoryTranslator


class Translator:
    """多后端翻译，自动故障转移"""

    LANG_MAP_GOOGLE = {
        'lebanon': 'ar',
        'egypt': 'ar',
        'syria': 'ar',
        'philippines': 'tl',  # 他加禄语 Tagalog
        'bangladesh': 'bn',
        'korea': 'ko',
        'english': 'en',
    }

    LANG_MAP_MYMEMORY = {
        'lebanon': 'ar-SA',
        'egypt': 'ar-EG',
        'syria': 'ar-SA',
        'philippines': 'fil-PH',
        'bangladesh': 'bn-IN',
        'korea': 'ko-KR',
        'english': 'en-GB',
    }

    # 后端顺序：MyMemory 更稳定不限流，Google 作为备选
    BACKEND_ORDER = ['MyMemory', 'Google']

    def __init__(self, source='lebanon', target='zh-CN'):
        self.source_key = source
        self.target = target
        self._min_interval = 0.5
        self._last_request_time = 0
        self._backoff_until = {}  # {backend_name: backoff_timestamp}

        self._backends = {}
        self._init_backends()

        print(f"[Translator] {self.source_key} -> {self.target}, "
              f"backends={list(self._backends.keys())}")

    def _init_backends(self):
        self._backends.clear()
        try:
            src = self.LANG_MAP_MYMEMORY.get(self.source_key, self.source_key)
            self._backends['MyMemory'] = MyMemoryTranslator(
                source=src, target=self.target)
        except Exception as e:
            print(f"[Translator] MyMemory init fail: {e}")

        try:
            src = self.LANG_MAP_GOOGLE.get(self.source_key, self.source_key)
            self._backends['Google'] = GoogleTranslator(
                source=src, target=self.target)
        except Exception as e:
            print(f"[Translator] Google init fail: {e}")

    def set_source(self, source):
        self.source_key = source
        self._backoff_until.clear()
        self._init_backends()
        print(f"[Translator] 切换为 {self.source_key} -> {self.target}")

    def translate(self, text: str) -> str:
        if not text or not text.strip():
            return ""

        # 限流
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

        # 按顺序尝试每个后端
        for name in self.BACKEND_ORDER:
            if name not in self._backends:
                continue

            # 检查是否在退避期
            if name in self._backoff_until and time.time() < self._backoff_until[name]:
                continue

            backend = self._backends[name]
            try:
                result = backend.translate(text)
                if result and result.strip():
                    return result.strip()
            except Exception as e:
                err_str = str(e).lower()
                if 'too many' in err_str or '429' in err_str or 'limit' in err_str:
                    # 速率限制 -> 长退避
                    self._backoff_until[name] = time.time() + random.uniform(10, 30)
                    print(f"[Translator] {name} 限流，退避 {self._backoff_until[name] - time.time():.0f}s")
                else:
                    print(f"[Translator] {name}: {str(e)[:100]}")
                time.sleep(0.2)

        return ""

    def translate_with_retry(self, text: str, max_retries=1) -> str:
        for attempt in range(max_retries + 1):
            result = self.translate(text)
            if result:
                return result
            if attempt < max_retries:
                wait = 2 ** attempt + random.uniform(0.5, 2)
                time.sleep(wait)
        return ""
