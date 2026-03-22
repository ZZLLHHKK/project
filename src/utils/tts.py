# src/utils/tts.py
import subprocess
import os
import shutil
from src.utils.config import PIPER_DIR, PIPER_EXE, TTS_MODEL


def _resolve_tts_paths() -> tuple[str, str]:
    """允許透過環境變數在執行中覆蓋 Piper 與模型路徑。"""
    piper_exe = os.environ.get("PIPER_EXE_PATH", str(PIPER_EXE)).strip()
    tts_model = os.environ.get("TTS_MODEL_PATH", str(TTS_MODEL)).strip()
    return piper_exe, tts_model

def speak(text: str) -> None:
    """
    使用 Piper TTS 將文字轉為語音並播放。
    具備開發模式：若找不到引擎，僅印出文字。
    """
    if not text:
        return
        
    text = text.strip()
    print(f"\n[PI 回覆]: {text}\n")
    
    piper_exe, tts_model = _resolve_tts_paths()

    # 防呆機制：檢查 Piper 執行檔是否存在 (避免在沒有環境的電腦上報錯)
    if not os.path.exists(piper_exe):
        print("[系統提示] 未偵測到 Piper 引擎，已略過實際語音播放。")
        return
        
    if not os.path.exists(tts_model):
        print("[系統提示] 未偵測到語音模型，請確認是否執行過 setup.sh。")
        return

    has_aplay = shutil.which("aplay") is not None
    has_ffplay = shutil.which("ffplay") is not None
    use_aplay = has_aplay

    # 若系統僅有 null 裝置（常見於 WSL 無音效輸出），先給清楚提示。
    try:
        devices = subprocess.check_output(["aplay", "-L"], text=True, stderr=subprocess.DEVNULL)
        real_devices = [line.strip() for line in devices.splitlines() if line and not line.startswith(" ") and line.strip() != "null"]
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

    # 為 piper 注入本地 lib 路徑，避免找不到 libpiper_phonemize.so 等動態庫。
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
            ["aplay", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"]
            if use_aplay
            else ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error", "-f", "s16le", "-ar", "22050", "-ac", "1", "-"],
            input=piper_proc.stdout,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        print(f"播放語音失敗: {e}")