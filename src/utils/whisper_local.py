from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import os
from typing import Optional
from faster_whisper import WhisperModel
from dotenv import load_dotenv
from src.utils.config import PROJECT_ROOT, MODELS_DIR

load_dotenv()  # 載入 .env 的 HF_TOKEN（避免下載警告）

@lru_cache(maxsize=2)
def _get_model(
    model_name_or_path: str,
    device: str = "cpu",
    compute_type: str = "int8",
    cpu_threads: int = 4
) -> WhisperModel:
    """
    快取載入 faster-whisper 模型（避免每次轉錄都重新載入）
    """
    return WhisperModel(
        model_name_or_path,
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads,
        num_workers=1  # Pi 4 建議設 1，避免記憶體過載
    )

def _normalize_language(language: Optional[str]) -> Optional[str]:
    if language is None:
        return None
    normalized = language.strip().lower()
    if normalized in {"", "auto", "none"}:
        return None
    return normalized

def transcribe_latest_wav(
    model_name: Optional[str] = None,  # 可傳模型名稱或本地路徑
    language: str = "auto",                    # 自動偵測中英
    threads: int = 4,                          # Pi 4 建議 4
    input_wav: Optional[str] = None,
    device: str = "cpu",
    compute_type: str = "int8",                # Pi 4 最快選擇
    beam_size: int = 3,                        # 速度與準確平衡
    best_of: int = 3,
    vad_filter: bool = True                    # 自動移除靜音
) -> str:
    """
    使用 faster-whisper 轉錄 latest.wav，返回辨識出的文字
    """
    if input_wav is None:
        input_wav = str(PROJECT_ROOT / "data" / "recordings" / "latest.wav")

    if not os.path.exists(input_wav):
        raise FileNotFoundError(f"找不到音檔：{input_wav}")

    # 預設使用設定檔中的模型（Hugging Face repo 名稱或本地路徑）
    if model_name is None:
        model_name = MODELS_DIR

    # 支援模型名稱或本地路徑
    if not os.path.isdir(model_name):
        # 如果是模型名稱（例如 "Systran/faster-whisper-tiny"），會自動下載
        pass
    else:
        print(f"使用本地模型路徑：{model_name}")

    model = _get_model(
        model_name,
        device=device,
        compute_type=compute_type,
        cpu_threads=threads
    )

    normalized_language = _normalize_language(language)

    try:
        segments, info = model.transcribe(
            input_wav,
            beam_size=beam_size,
            best_of=best_of,
            language=normalized_language,
            vad_filter=vad_filter,
            vad_parameters=dict(min_silence_duration_ms=500),  # 靜音超過 0.5 秒切段
            condition_on_previous_text=True,                    # 用前文上下文
            word_timestamps=False                               # 不需要單字時間戳
        )

        text_parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
        text = " ".join(text_parts).strip()

        #print(f"偵測語言：{info.language}，信心：{info.language_probability:.2f}")
        return text if text else "[無辨識結果]"

    except Exception as e:
        raise RuntimeError(f"轉錄過程錯誤：{str(e)}")