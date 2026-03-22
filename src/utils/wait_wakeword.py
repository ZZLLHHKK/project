import os
import struct
from pathlib import Path

try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv(*_args, **_kwargs):
        return False

# 載入 .env 變數
load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2] 
PPN_PATHS = [
    BASE_DIR / "models" / "wakeword.ppn",
    BASE_DIR / "data" / "models" / "wakeword.ppn",
]

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

    # 檢查 .ppn 檔案是否存在（優先使用專案根目錄 models/）
    ppn_path = next((p for p in PPN_PATHS if p.exists()), None)
    if ppn_path is None:
        print("錯誤: 找不到 wakeword.ppn 模型檔")
        print(f"已檢查路徑: {PPN_PATHS[0]}、{PPN_PATHS[1]}")
        return False

    porcupine = None
    pa = None
    audio_stream = None

    try:
        # 初始化 Porcupine
        porcupine = pvporcupine.create(access_key=access_key, keyword_paths=[str(ppn_path)])
        pa = pyaudio.PyAudio()

        # 開啟麥克風串流
        audio_stream = pa.open(
            rate=porcupine.sample_rate,
            channels=1,
            format=pyaudio.paInt16,
            input=True,
            frames_per_buffer=porcupine.frame_length
        )

        # 開始無限迴圈，監聽聲音
        while True:
            # 讀取麥克風資料
            pcm = audio_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm = struct.unpack_from("h" * porcupine.frame_length, pcm)

            # 將聲音特徵交給喚醒引擎判斷
            result = porcupine.process(pcm)

            # result >= 0 代表偵測到喚醒詞
            if result >= 0:
                return True

    except Exception as e:
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