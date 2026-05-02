# src/utils/tts.py
import re
import subprocess
import os
import shutil
from src.utils.config import PIPER_DIR, PIPER_EXE, TTS_MODEL, TTS_MODEL_EN

# ---------------------------------------------------------------------------
# 數字→中文 輔助（用於時間朗讀）
# ---------------------------------------------------------------------------
_ZH_DIGITS = "零一二三四五六七八九"


def _num_to_zh(n: int) -> str:
    if n < 10:
        return _ZH_DIGITS[n]
    tens, ones = n // 10, n % 10
    if tens == 1:
        return "十" + (_ZH_DIGITS[ones] if ones else "")
    return _ZH_DIGITS[tens] + "十" + (_ZH_DIGITS[ones] if ones else "")


# ---------------------------------------------------------------------------
# 文字前處理：將特殊符號轉成 TTS 可正確朗讀的格式
# ---------------------------------------------------------------------------
_TEMP_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s*(?:°C|℃|度[Cc]?)")
_TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")


def _normalize_zh(text: str) -> str:
    """中文朗讀前處理：溫度符號 / 時間格式 → 口語化中文。"""
    def _temp(m: re.Match) -> str:
        val = round(float(m.group(1)))
        return f"攝氏{_num_to_zh(val)}度"

    def _time(m: re.Match) -> str:
        h, mi = int(m.group(1)), int(m.group(2))
        if mi == 0:
            return f"{_num_to_zh(h)}點"
        return f"{_num_to_zh(h)}點{_num_to_zh(mi)}分"

    text = _TEMP_RE.sub(_temp, text)
    text = _TIME_RE.sub(_time, text)
    return text


def _normalize_en(text: str) -> str:
    """英文朗讀前處理：溫度符號 / 時間格式 → 自然英文。"""
    def _temp(m: re.Match) -> str:
        val = m.group(1).rstrip("0").rstrip(".")
        return f"{val} degrees Celsius"

    def _time(m: re.Match) -> str:
        h, mi = int(m.group(1)), int(m.group(2))
        if mi == 0:
            return f"{h} o'clock"
        return f"{h} {mi:02d}"

    text = _TEMP_RE.sub(_temp, text)
    text = _TIME_RE.sub(_time, text)
    return text


# ---------------------------------------------------------------------------
# 路徑解析：依語言選擇對應模型
# ---------------------------------------------------------------------------
def _resolve_tts_paths(lang: str = "zh") -> tuple[str, str]:
    """允許透過環境變數在執行中覆蓋 Piper 與模型路徑。"""
    piper_exe = os.environ.get("PIPER_EXE_PATH", str(PIPER_EXE)).strip()

    if lang == "en":
        default_model = str(TTS_MODEL_EN)
        tts_model = os.environ.get("TTS_MODEL_EN_PATH", default_model).strip()
    else:
        default_model = str(TTS_MODEL)
        tts_model = os.environ.get("TTS_MODEL_PATH", default_model).strip()

    return piper_exe, tts_model


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------
def speak(text: str, lang: str = "zh") -> None:
    """
    使用 Piper TTS 將文字轉為語音並播放。
    lang: "zh"（中文）或 "en"（英文），用於選擇模型與文字前處理。
    具備開發模式：若找不到引擎，僅印出文字。
    """
    if not text:
        return

    text = text.strip()
    print(f"\n[PI 回覆]: {text}\n")

    # 文字前處理（轉換特殊符號）
    text = _normalize_en(text) if lang == "en" else _normalize_zh(text)

    piper_exe, tts_model = _resolve_tts_paths(lang)

    if not os.path.exists(piper_exe):
        print("[系統提示] 未偵測到 Piper 引擎，已略過實際語音播放。")
        return

    if not os.path.exists(tts_model):
        lang_label = "英文" if lang == "en" else "中文"
        print(f"[系統提示] 未偵測到{lang_label}語音模型：{tts_model}")
        return

    has_aplay = shutil.which("aplay") is not None
    has_ffplay = shutil.which("ffplay") is not None
    use_aplay = has_aplay

    try:
        devices = subprocess.check_output(["aplay", "-L"], text=True, stderr=subprocess.DEVNULL)
        real_devices = [
            line.strip() for line in devices.splitlines()
            if line and not line.startswith(" ") and line.strip() != "null"
        ]
        if not real_devices:
            use_aplay = False
    except Exception:
        pass

    if not use_aplay and not has_ffplay:
        if not has_aplay:
            print("[系統提示] 未偵測到 aplay，請先安裝：sudo apt install -y alsa-utils")
        else:
            print("[系統提示] 目前沒有可用的 ALSA 播放裝置（aplay 只偵測到 null）。")
            print("[系統提示] 可安裝 ffplay 作為替代：sudo apt install -y ffmpeg")
        return

    env = os.environ.copy()
    existing = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = f"{PIPER_DIR}:{existing}" if existing else str(PIPER_DIR)

    try:
        piper_proc = subprocess.run(
            [str(piper_exe), "--model", str(tts_model), "--output-raw"],
            input=(text + "\n").encode("utf-8"),
            capture_output=True,
            check=True,
            env=env,
        )
        subprocess.run(
            ["aplay", "-D", "plughw:0,0", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"]
            if use_aplay
            else ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-f", "s16le", "-ar", "22050", "-ac", "1", "-"],
            input=piper_proc.stdout,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        print(f"播放語音失敗: {e}")
