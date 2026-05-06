# src/utils/tts.py
import subprocess
import os
import shutil
import sys
from pathlib import Path
from src.utils.config import PIPER_DIR, PIPER_EXE, TTS_MODEL

# Piper Windows EXE 無法處理包含非 ASCII 字元的路徑參數，
# 因此在 Windows 上透過 subst 建立暫時磁碟代號以繞過此限制。
_SUBST_DRIVE = "Q:"


def _resolve_tts_paths() -> tuple[str, str]:
    """允許透過環境變數在執行中覆蓋 Piper 與模型路徑。"""
    piper_exe = os.environ.get("PIPER_EXE_PATH", str(PIPER_EXE)).strip()
    tts_model = os.environ.get("TTS_MODEL_PATH", str(TTS_MODEL)).strip()
    return piper_exe, tts_model


def _make_ascii_paths(piper_exe: str, tts_model: str, espeak_data: str) -> tuple[str, str, str, bool]:
    """
    Windows：若路徑含非 ASCII 字元，用 subst 建立暫時磁碟代號。
    回傳 (piper_exe, tts_model, espeak_data, subst_created)。
    """
    project_root = Path(piper_exe).parent.parent  # .../project
    subst_created = False
    try:
        subprocess.run(["subst", _SUBST_DRIVE, str(project_root)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subst_created = True
        def remap(p: str) -> str:
            try:
                rel = Path(p).relative_to(project_root)
                return str(Path(_SUBST_DRIVE + "\\") / rel)
            except ValueError:
                return p
        return remap(piper_exe), remap(tts_model), remap(espeak_data), True
    except Exception:
        return piper_exe, tts_model, espeak_data, False


def _remove_subst() -> None:
    try:
        subprocess.run(["subst", _SUBST_DRIVE, "/D"],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


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

    if not os.path.exists(piper_exe):
        print("[系統提示] 未偵測到 Piper 引擎，已略過實際語音播放。")
        return

    if not os.path.exists(tts_model):
        print("[系統提示] 未偵測到語音模型，請確認是否執行過 setup.sh。")
        return

    is_windows = sys.platform == "win32"
    has_ffplay = shutil.which("ffplay") is not None
    use_ffplay = False

    if is_windows:
        if not has_ffplay:
            print("[系統提示] 未偵測到 ffplay，請安裝 FFmpeg 並加入 PATH。")
            return
        use_ffplay = True
    else:
        has_aplay = shutil.which("aplay") is not None
        use_aplay = has_aplay
        try:
            devices = subprocess.check_output(["aplay", "-L"], text=True, stderr=subprocess.DEVNULL)
            real_devices = [line.strip() for line in devices.splitlines()
                            if line and not line.startswith(" ") and line.strip() != "null"]
            if not real_devices:
                use_aplay = False
        except Exception:
            pass
        if not use_aplay:
            if not has_aplay:
                print("[系統提示] 未偵測到 aplay，請先安裝：sudo apt install -y alsa-utils")
            elif not has_ffplay:
                print("[系統提示] 目前沒有可用的 ALSA 播放裝置（aplay 只偵測到 null）。")
                print("[系統提示] 可安裝 ffplay 作為替代：sudo apt install -y ffmpeg")
                return
            else:
                use_ffplay = True

    env = os.environ.copy()
    if not is_windows:
        existing = env.get("LD_LIBRARY_PATH", "")
        env["LD_LIBRARY_PATH"] = f"{PIPER_DIR}:{existing}" if existing else str(PIPER_DIR)

    espeak_data = os.environ.get("ESPEAK_DATA_PATH", str(PIPER_DIR / "espeak-ng-data")).strip()

    subst_created = False
    try:
        if is_windows:
            piper_exe, tts_model, espeak_data, subst_created = _make_ascii_paths(
                piper_exe, tts_model, espeak_data
            )

        piper_cmd = [piper_exe, "--model", tts_model, "--output-raw"]
        if os.path.isdir(espeak_data):
            piper_cmd += ["--espeak-data", espeak_data]

        piper_proc = subprocess.Popen(
            piper_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            env=env,
        )
        audio_data, _ = piper_proc.communicate(input=(text + "\n").encode("utf-8"))

        if not audio_data:
            print("播放語音失敗: Piper 未產生音訊")
            return

        if use_ffplay:
            play_cmd = ["ffplay", "-nodisp", "-autoexit", "-loglevel", "error",
                        "-f", "s16le", "-ar", "22050", "-ch_layout", "mono", "-"]
        else:
            play_cmd = ["aplay", "-D", "plughw:1,0", "-r", "22050", "-f", "S16_LE", "-t", "raw", "-"]

        subprocess.run(
            play_cmd,
            input=audio_data,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError as e:
        print(f"播放語音失敗: {e}")
    finally:
        if subst_created:
            _remove_subst()
