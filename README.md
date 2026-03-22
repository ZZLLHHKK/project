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
