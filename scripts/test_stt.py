import sys
from pathlib import Path
# 測試解析音檔流程

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.audio import stt_pipeline
from src.utils.config import DEVICE_PORT

print("測試完整 STT 流程...")
text = stt_pipeline(duration=4, device=DEVICE_PORT)

if text:
    print("\n最終結果:")
    print(text)
else:
    print("整個流程失敗")