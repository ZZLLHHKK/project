# 本地語音家電控制專案

這是一個以 Python 為核心、同時支援桌面測試與 Raspberry Pi 實機部署的語音控制系統。

核心設計目標：

- 同一份核心流程，透過 runtime mode 切換 desktop 或 hardware
- 語音輸入失敗時可自動降級為鍵盤輸入，不中斷互動
- 以 Piper 作為本地 TTS，支援模型切換與播放 fallback
- 對 LLM 配額與錯誤提供可用的降級行為

## 快速開始

1. Clone 專案

   ```bash
   git clone https://github.com/ZZLLHHKK/project.git
   cd project
   ```

2. 一鍵安裝（桌面）

   ```bash
   bash setup.sh --mode desktop
   ```

3. 設定環境變數

   ```bash
   cp .env.example .env
   ```

4. 啟動

   ```bash
   source .venv/bin/activate
   python -m src.main
   ```

## 部署模式

### Desktop / WSL 模式

- 適用於功能開發、流程驗證、語音回覆測試
- 預設策略：鍵盤喚醒詞 + 語音命令 + Piper TTS
- 安裝指令：

   ```bash
  bash setup.sh --mode desktop
   ```

### Raspberry Pi 硬體模式

- 適用於 GPIO 連接 LED / FAN / 7-seg / DHT11
- 安裝指令：

   ```bash
  bash setup.sh --mode pi
   ```

## 專案結構（精簡版）

```text
project/
├── src/
│   ├── main.py              # Desktop 入口（薄入口）
│   ├── true_main.py         # 單一核心流程
│   ├── audio/               # 語音輸入處理
│   ├── llm/                 # LLM 封裝與提示詞
│   ├── devices/             # GPIO 硬體控制
│   ├── core/                # agent/router/state/validator
│   └── utils/               # config/tts/file_io/sox/whisper
├── data/
│   ├── models/              # voice.onnx, wakeword 模型
│   ├── memory/              # short/long term memory
│   └── recordings/          # 錄音檔
├── requirements/
│   ├── base.txt
│   ├── desktop.txt
│   ├── pi.txt
│   └── dev.txt
├── setup.sh
└── .env.example
```

## 執行時控制指令

程式啟動後可用以下指令切換模式：

- /help：顯示指令
- /k：切到鍵盤命令輸入
- /v：切到語音命令輸入
- /mode voice|keyboard：設定命令輸入模式
- /rec 秒數：調整命令錄音秒數（1 到 15）
- /voice：查看目前 TTS 模型
- /voice 路徑：切換 TTS 模型
- /status：查看目前狀態
- /standby：進入待機
- /exit：離開

## 依賴安裝策略

已改為分層 requirements：

- requirements/base.txt：核心依賴
- requirements/desktop.txt：桌面開發環境
- requirements/pi.txt：樹莓派硬體依賴
- requirements/dev.txt：測試與開發工具

若手動安裝：

```bash
source .venv/bin/activate
pip install -r requirements/desktop.txt
```

Pi：

```bash
source .venv/bin/activate
pip install -r requirements/pi.txt
```

## 環境變數

請參考 .env.example，至少需要：

- GEMINI_API_KEY
- RUNTIME_MODE（desktop 或 hardware）
- SPEECH_ENABLED / WAKEWORD_ENABLED / TTS_ENABLED / DHT11_ENABLED
- DEVICE_PORT

可選：

- PIPER_EXE_PATH
- TTS_MODEL_PATH

## 大檔案管理建議

目前語音模型與 Piper runtime 屬於大型資源，建議：

- 優先由 setup.sh 下載，不直接長期跟隨 Git 歷史
- 或導入 Git LFS 管理模型檔

## 常見問題

1. push 成功但出現 large file warning

- 代表已推送成功，僅提醒檔案大於 GitHub 建議上限 50MB

2. WSL 錄音或播放異常

- 先確認 ffmpeg 可用
- 若 ALSA 裝置只有 null，TTS 會使用 ffplay fallback

3. 額度不足

- LLM 層會回傳 quota_exceeded 降級狀態，可先用 fastpath 或鍵盤流程繼續測試

## STT 量測流程（第一階段）

### 1) 準備測試題庫與音檔

- 題庫檔案：`data/eval/test_cases.csv`
- 音檔資料夾：`data/recordings/`
- `test_cases.csv` 的 `audio_file` 需對應到 `data/recordings/` 內的 WAV 檔

### 2) 安裝量測依賴

```bash
source .venv/bin/activate
pip install -r requirements/dev.txt
```

### 2.5) 自動錄音與自動命名（建議）

直接依 `data/eval/test_cases.csv` 逐題錄音，檔名自動使用 `audio_file` 欄位（例如 `T_001.wav`）。

```bash
python scripts/record_eval_audio.py \
   --cases data/eval/test_cases.csv \
   --output-dir data/recordings/eval \
   --duration 6
```

常用選項：

- `--start-id T_020`：從指定題號開始續錄
- `--overwrite`：覆蓋既有音檔

錄完後，執行 STT 評測時改用該資料夾：

```bash
python scripts/eval_stt.py --audio-dir data/recordings/eval
```

### 3) 執行 STT 評測

```bash
python scripts/eval_stt.py \
   --cases data/eval/test_cases.csv \
   --audio-dir data/recordings \
   --output data/eval/results.csv \
   --models tiny,base,small \
   --repeat 3 \
   --device cpu \
   --compute-type int8 \
   --threads 4
```

輸出欄位包含：

- `cer`：字錯率
- `rtf`：即時率
- `inference_ms`：單次推論耗時
- `startup_state`：`Cold` / `Warm`

### 4) 匯總平均與 P95

```bash
python scripts/summarize_stt_results.py \
   --input data/eval/results.csv \
   --output data/eval/summary_by_model.csv
```

若只想看熱啟動結果：

```bash
python scripts/summarize_stt_results.py --warm-only
```

## 第二階段前置（指令理解與流程耗時）

### 1) NLU 題庫與格式

- 題庫檔案：`data/eval/nlu_test_cases.csv`
- 單次結果：`data/eval/nlu_results.csv`
- 指標彙總：`data/eval/nlu_summary.csv`
- 流程耗時表：`data/eval/pipeline_timing.csv`

`nlu_test_cases.csv` 建議欄位：

- `test_id`
- `input_text`
- `expected_route`（`fastpath` / `gemini`）
- `expected_actions_json`
- `utterance_type`
- `noise_level`
- `note`

### 2) 執行 NLU 評測（預設僅測 FastPath）

```bash
python scripts/eval_nlu_pipeline.py \
   --cases data/eval/nlu_test_cases.csv \
   --output data/eval/nlu_results.csv \
   --summary data/eval/nlu_summary.csv \
   --repeat 3
```

若要同時測 Gemini fallback：

```bash
python scripts/eval_nlu_pipeline.py --enable-gemini
```

### 3) 單獨重算 NLU 彙總

```bash
python scripts/summarize_nlu_results.py \
   --input data/eval/nlu_results.csv \
   --output data/eval/nlu_summary.csv
```

`nlu_summary.csv` 會輸出：

- `route_match_rate`
- `action_match_rate`
- `execution_success_rate`
- `fastpath_hit_rate`
- `mean_parse_ms` / `p95_parse_ms`

### 4) 流程耗時資料使用方式

`pipeline_timing.csv` 用來整合完整流程耗時（錄音、STT、解析、執行、TTS、端到端），可由主流程執行後落表：

- `record_ms`
- `stt_ms`
- `parse_ms`
- `action_ms`
- `tts_ms`
- `end_to_end_ms`
- `success`
- `fail_stage`
