import sys
from pathlib import Path
# 測試樹莓派錄音功能

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.audio import record_with_arecord
from src.utils.config import DEVICE_PORT

print("測試 arecord 錄音...")
wav_path = record_with_arecord(duration=6, device=DEVICE_PORT)  # 改 device

if wav_path:
    print(f"成功錄到：{wav_path}")
else:
    print("錄音失敗，請檢查裝置編號或麥克風")