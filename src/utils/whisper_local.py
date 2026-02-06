"""Local speech-to-text via faster-whisper."""

from functools import lru_cache
from pathlib import Path
import os
from typing import Optional

from faster_whisper import WhisperModel
from src.utils.config import PROJECT_ROOT, MODELS_DIR


@lru_cache(maxsize=2)
def _get_model(model_name: str, device: str, compute_type: str, cpu_threads: int) -> WhisperModel:
    return WhisperModel(
        model_name,
        device=device,
        compute_type=compute_type,
        cpu_threads=cpu_threads
    )


def _normalize_language(language: Optional[str]) -> Optional[str]:
    if language is None:
        return None
    normalized = language.strip().lower()
    if normalized in {"", "auto", "none"}:
        return None
    return normalized


def transcribe_latest_wav(
    model_name: str = MODELS_DIR,
    language: str = "auto",  # 中英支援
    threads: int = 4,
    input_wav: Optional[str] = None,
    device: str = "cpu",
    compute_type: str = "int8"
) -> str:
    """
    使用 faster-whisper 轉錄 latest.wav, 返回辨識出的文字
    """
    if input_wav is None:
        input_wav = str(PROJECT_ROOT / "data" / "recordings" / "latest.wav")

    if not os.path.exists(input_wav):
        raise FileNotFoundError(f"找不到音檔：{input_wav}")

    if isinstance(model_name, Path):
        model_name = str(model_name)
    if str(model_name).endswith(".bin"):
        raise ValueError("faster-whisper 不支援 ggml .bin 模型，請改用模型名稱或 CTranslate2 路徑")

    model = _get_model(model_name, device=device, compute_type=compute_type, cpu_threads=threads)
    normalized_language = _normalize_language(language)

    try:
        segments, _info = model.transcribe(
            input_wav,
            language=normalized_language,
            beam_size=3,
            best_of=3,
            vad_filter=True,
            condition_on_previous_text=False,
            word_timestamps=False
        )
        text_parts = [seg.text.strip() for seg in segments if seg.text and seg.text.strip()]
        text = " ".join(text_parts).strip()
        return text if text else "[無辨識結果]"
    except Exception as e:
        raise RuntimeError(f"轉錄過程錯誤：{str(e)}")