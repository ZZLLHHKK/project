# whisper.cpp 使用筆記
（重點：離線 .wav 轉文字）
適用於 Raspberry Pi、Linux 等環境的本地語音轉文字工具（基於 OpenAI Whisper 的 C++ 實作）

本筆記強調**單純把 WAV 檔案轉成文字**（非即時麥克風 STT），使用 `whisper-cli` 指令。

## 前置作業

### Step 1：基本安裝與模型下載
```bash
# 建議放在 ~/whisper.cpp 或 ~/Desktop/whisper.cpp
git clone https://github.com/ggml-org/whisper.cpp.git
cd whisper.cpp

# 下載英文模型（從小到大測試：tiny.en → base.en → small.en）
# 模型大小與記憶體需求：https://github.com/ggml-org/whisper.cpp?tab=readme-ov-file#memory-usage
bash ./models/download-ggml-model.sh tiny
bash ./models/download-ggml-model.sh base
bash ./models/download-ggml-model.sh small
# 或 tiny.en（Pi 最省資源）、small.en（更準確）
```

### Step 2：安裝 SDL2（如果之後想用即時功能才需要，離線轉檔可跳過）
```bash
sudo apt update
sudo apt install -y libsdl2-dev libsdl2-2.0-0
```

### Step 3：編譯（啟用 SDL2 支援，離線轉檔也適用）
```bash
cd ~/whisper.cpp  # 調整成你的路徑
sudo apt install cmake #如果沒裝的話
cmake -B build -DWHISPER_SDL2=ON
cmake --build build --config Release -j4
# Raspberry Pi 建議 -j 值：
# Pi 3 → -j2（最安全，避免過熱/死機）
# Pi 4 → -j4（無風扇最穩）或 -j3（有散熱風扇可試）
# Pi 5 → -j4 ~ -j6
```

編譯完成後，可執行檔在 `build/bin/`：
- `whisper-cli` → 用來把 WAV 檔案轉成文字（這是重點！）
- `whisper-stream` → 即時麥克風（可忽略，如果你不要 STT）

看到這裡，基本上就可以用了

## 常用指令（離線 WAV 轉文字）

所有指令建議在 `build/bin` 目錄下執行，或使用完整路徑 `./build/bin/whisper-cli`。

### 基本單行指令（輸出到終端機）
```bash
cd build/bin && ./whisper-cli -m ../models/ggml-base.en.bin -f ../meeting.wav
```

### 推薦用法（輸出純文字到 .txt 檔案，無時間戳）
```bash
cd build/bin && ./whisper-cli -m ../models/ggml-base.en.bin -f ../meeting.wav -otxt --language en --output-txt ../meeting-transcript.txt -t 4
```
- `-m`：模型路徑（必填）
- `-f`：輸入 WAV 檔案（**必須是 16kHz 單聲道 16-bit PCM WAV**）
- `-otxt`：輸出純文字（.txt 檔，與輸入檔同目錄，或用 `--output-txt` 指定）
- `--language en`：強制英文（或 `auto`、`zh` 等）
- `-t 4`：執行緒數（Pi 4 建議 2~4，依 CPU 調整）
- 其他常用選項：
  - `--no-timestamps`：不要輸出時間戳（更乾淨的文字）
  - `--translate`：翻譯成英文（非英文音檔用）
  - `-ml 0`：不限制每段長度（適合長句）

### 如果音檔不是 WAV，先轉檔（用 ffmpeg）
```bash
ffmpeg -i input.mp3 -ar 16000 -ac 1 -c:a pcm_s16le output.wav
```

## 注意事項（離線轉錄重點）

1. **音檔格式限制**  
   只接受 **16kHz 單聲道 16-bit PCM WAV**。其他格式（mp3、m4a、wav 但取樣率錯）都要用 ffmpeg 轉。

2. **Raspberry Pi 編譯穩定性**  
   - Pi 3：務必 `-j1`，否則容易過熱/死機  
   - Pi 4：`-j2`（無風扇最穩）或 `-j3`（加風扇可試）  
   - 記憶體不足可加 swapfile，但編譯會變超慢

3. **模型選擇建議**（Pi 上）  
   - tiny.en → 最快、最省 RAM/CPU，適合 Pi 測試  
   - base.en → 平衡，推薦入門  
   - small.en → 準確度明顯更好，但 RAM/CPU 吃較多  
   - large-v3 → Pi 幾乎跑不動，建議 PC

4. **語言模型**  
   `.en` 只適合英文，效果最佳  
   多語言/中英混雜 → 下載不帶 `.en` 的版本（base / small），但 Pi 上建議用 small 以下

5. **常見錯誤**  
   - `failed to read WAV file` 或取樣率錯誤 → 用 ffmpeg 轉成 16kHz mono  
   - 結果亂碼 → 檢查 `--language` 是否正確，或換 `.en` 模型  
   - 速度慢 → 用量化模型（q5_0 / q5_1，從 Hugging Face 下載 ggml-*-q5_0.bin）

6. **效能調優**  
   - 量化模型更省記憶體/更快（e.g. ggml-base.en-q5_0.bin）  
   - Pi 上關閉其他程式，避免同時高負載  
   - 長檔案建議加 `-t` 提高執行緒（但別超過核心數太多）
