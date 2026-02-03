# src/utils/whisper_local.py
import subprocess
import os
from pathlib import Path

from src.utils.config import PROJECT_ROOT, WHISPER_DIR, WHISPER_MAIN, MODELS_DIR

def transcribe_latest_wav(
    model_name: str = MODELS_DIR,
    language: str = "auto",  # 中英支援
    threads: int = 4, # 樹莓派支援4 thread
    input_wav: str = None
) -> str:
    """
    使用 whisper.cpp 轉錄 latest.wav, 返回辨識出的文字
    """
    if input_wav is None:
        input_wav = str(PROJECT_ROOT / "data" / "recordings" / "latest.wav")

    model_path = MODELS_DIR / model_name
    if not model_path.exists():
        raise FileNotFoundError(f"模型不存在：{model_path}")

    if not WHISPER_MAIN.exists():
        raise FileNotFoundError(f"找不到 main 執行檔：{WHISPER_MAIN}")

    if not os.path.exists(input_wav):
        raise FileNotFoundError(f"找不到音檔：{input_wav}")

    cmd = [
        str(WHISPER_MAIN),
        "-m", str(model_path),
        "-l", language,
        "-t", str(threads),
        "-f", input_wav,
        # 可選：加快速度、減少雜訊
        "--beam-size", "3",
        "--best-of", "3",
        # "--no-timestamps",          # 如果不要時間戳
    ]

    # print(f"開始使用 whisper.cpp 轉錄：{input_wav}")
    # print(f"模型：{model_name}，語言：{language}，執行緒：{threads}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=120          # 避免卡死，樹莓派上 small 模型通常 10-30 秒
        )

        output = result.stdout.strip()

        # whisper.cpp 輸出格式：通常最後幾行是辨識結果
        # 簡單提取：取最後非空、非 [ 開頭的行
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if lines:
            text = lines[-1]  # 最後一行通常是最終結果
            # 如果有時間戳，可再清理
            if text.startswith('['):
                text = text.split(']')[-1].strip()
            return text
        else:
            return "[無辨識結果]"

    except subprocess.TimeoutExpired:
        raise RuntimeError("轉錄超時（樹莓派可能太慢，試試 tiny 模型）")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"whisper.cpp 執行失敗：{e.stderr}")
    except Exception as e:
        raise RuntimeError(f"轉錄過程錯誤：{str(e)}")