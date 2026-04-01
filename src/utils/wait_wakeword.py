import os
import struct
import platform
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*_args, **_kwargs):
        return False

# 載入 .env 變數
load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2] 
LEGACY_PPN_PATHS = [
    BASE_DIR / "models" / "wakeword.ppn",
    BASE_DIR / "data" / "models" / "wakeword.ppn",
]


def _detect_platform_tag() -> str:
    """將當前作業系統/架構映射到 wakeword 模型資料夾名稱。"""
    sys_name = platform.system().lower()
    machine = platform.machine().lower()

    if sys_name == "linux":
        if machine in ("x86_64", "amd64"):
            return "linux_x86_64"
        if machine in ("aarch64", "arm64", "armv7l", "armv6l"):
            return "raspberry_pi"
        return f"linux_{machine}"

    if sys_name == "darwin":
        if machine in ("arm64", "aarch64"):
            return "mac_arm64"
        return "mac_x86_64"

    if sys_name == "windows":
        return "windows_x86_64"

    return f"{sys_name}_{machine}"


def _build_ppn_candidates() -> list[Path]:
    """建立 .ppn 候選清單：手動覆蓋 > 平台路徑 > 舊版相容路徑。"""
    override = (os.getenv("WAKEWORD_PPN_PATH") or "").strip()
    if override:
        return [Path(override)]

    platform_tag = _detect_platform_tag()
    candidates = [
        BASE_DIR / "data" / "models" / "wakeword" / platform_tag / "wakeword.ppn",
        BASE_DIR / "models" / "wakeword" / platform_tag / "wakeword.ppn",
    ]
    candidates.extend(LEGACY_PPN_PATHS)
    return candidates


def _resolve_ppn_path() -> tuple[Path | None, list[Path], str]:
    candidates = _build_ppn_candidates()
    for p in candidates:
        if p.exists():
            return p, candidates, _detect_platform_tag()
    return None, candidates, _detect_platform_tag()

def wait_for_wake_word():
    """
    阻塞程式，直到聽到指定的喚醒詞為止。
    """
    access_key = os.getenv("PICOVOICE_API_KEY")

    try:
        import pvporcupine
        import pyaudio
    except Exception as e:
        print(f"錯誤: 喚醒詞套件未安裝或不可用: {e}")
        return False

    if not access_key:
        print("錯誤: 找不到 PICOVOICE_API_KEY，請檢查 .env 檔案")
        return False

    # 檢查 .ppn 檔案是否存在（支援平台專用路徑 + 舊版路徑）
    ppn_path, ppn_candidates, platform_tag = _resolve_ppn_path()
    if ppn_path is None:
        print("錯誤: 找不到 wakeword.ppn 模型檔")
        print(f"建議平台模型: {platform_tag}")
        print("已檢查路徑:")
        for p in ppn_candidates:
            print(f"  - {p}")
        print("可用環境變數 WAKEWORD_PPN_PATH 指定自訂模型路徑")
        return False

    print(f"[Wakeword] 使用模型: {ppn_path}")

    porcupine = None
    pa = None
    audio_stream = None

    try:
        # 壓掉 ALSA 無害警告訊息
        import ctypes
        try:
            ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p)
            c_error_handler = ERROR_HANDLER_FUNC(lambda *_: None)
            asound = ctypes.cdll.LoadLibrary('libasound.so.2')
            asound.snd_lib_error_set_handler(c_error_handler)
        except Exception:
            pass

        porcupine = pvporcupine.create(access_key=access_key, keyword_paths=[str(ppn_path)])
        pa = pyaudio.PyAudio()

        # 自動尋找 USB 麥克風裝置
        input_device_index = None
        for i in range(pa.get_device_count()):
            info = pa.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0 and 'USB' in info.get('name', ''):
                input_device_index = i
                break

        if input_device_index is None:
            print("錯誤: 找不到 USB 麥克風裝置")
            return False

        print(f"[Wakeword] 使用麥克風裝置: index={input_device_index}")


        DEVICE_RATE = 48000
        PORCUPINE_RATE = porcupine.sample_rate  # 16000
        RATIO = DEVICE_RATE // PORCUPINE_RATE   # 3

        # 用裝置原生 48000 Hz 開啟麥克風
        audio_stream = pa.open(
            rate=DEVICE_RATE,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            input_device_index=input_device_index,
            frames_per_buffer=porcupine.frame_length * RATIO
        )

        while True:
            pcm = audio_stream.read(porcupine.frame_length * RATIO, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * (porcupine.frame_length * RATIO), pcm)

            # 每 3 個取樣點取 1 個，降採樣 48000 → 16000
            downsampled = pcm[::RATIO]

            result = porcupine.process(downsampled)
            if result >= 0:
                return True

    except Exception as e:
        msg = str(e)
        if "belongs to a different platform" in msg or "INVALID_ARGUMENT" in msg:
            print("喚醒詞引擎發生錯誤: .ppn 平台不相容")
            print(f"當前建議平台模型: {platform_tag}")
            print(f"目前使用模型: {ppn_path}")
            print("請下載對應平台的 wakeword.ppn，或設定 WAKEWORD_PPN_PATH")
        else:
            print(f"喚醒詞引擎發生錯誤: {e}")
        return False

    finally:
        # 安全關閉所有資源
        if audio_stream is not None:
            audio_stream.close()
        if pa is not None:
            pa.terminate()
        if porcupine is not None:
            porcupine.delete()