# 智慧家庭語音控制系統

以 Python 為核心的智慧家庭控制專案，支援中英文雙語語音輸入與 GUI 操作，可部署於 Raspberry Pi 並透過 GPIO 控制實體硬體。

## 系統功能

- **語音辨識**：使用 faster-whisper 進行本地語音轉文字，支援中英文自動偵測
- **自然語言理解**：FastPath 規則引擎處理常見指令，複雜語意交由 Gemini API 解析
- **硬體控制**：透過 GPIO 控制 LED 燈（廚房／客廳／客房）、風扇、七段顯示器、DHT11 溫濕度感測器
- **排程管理**：支援每日定時、單次、每週排程，可設定幾分鐘後執行的相對時間排程
- **使用者習慣學習**：可教導系統自訂詞語對應（如「睡覺了」→「全部關燈、關風扇」）
- **本地 TTS**：使用 Piper 語音引擎，支援中文（voice.onnx）與英文（en_US-lessac-medium.onnx）
- **圖形介面**：Tkinter GUI，支援中英文切換，單一視窗頁面導覽

## 硬體需求

| 元件 | 規格 |
|------|------|
| 主控板 | Raspberry Pi 4 |
| LED | 紅（廚房 GPIO22）、綠（客廳 GPIO10）、黃（客房 GPIO9） |
| 風扇 | 繼電器模組（GPIO16） |
| 七段顯示器 | 共陽極，顯示目標溫度 |
| 溫濕度感測器 | DHT11（GPIO25） |
| 麥克風 | USB 麥克風（ALSA 裝置） |
| 喇叭 | 3.5mm 音源輸出（bcm2835 Headphones） |

## 快速開始

### 1. Clone 專案

```bash
git clone https://github.com/ZZLLHHKK/project.git
cd project
```

### 2. 安裝依賴

```bash
bash scripts/setup.sh --mode pi       # 樹莓派
bash scripts/setup.sh --mode desktop  # 桌面開發
```

### 3. 設定環境變數

在 `project/` 根目錄建立 `.env` 檔案：

```env
GEMINI_API_KEY=your_api_key_here
RUNTIME_MODE=hardware          # hardware 或 desktop
SPEECH_ENABLED=1
WAKEWORD_ENABLED=1
TTS_ENABLED=1
DHT11_ENABLED=1
DEVICE_PORT=plughw:3,0         # 麥克風 ALSA 裝置（用 arecord -l 確認）
TTS_DEVICE=plughw:2,0          # 喇叭 ALSA 裝置（用 aplay -l 確認）
```

### 4. 下載語音模型（首次使用）

```bash
# 中文 TTS 模型
wget -P data/models/ https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_TW/medium/zh_TW-medium.onnx

# 英文 TTS 模型
wget -P data/models/ https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
```

### 5. 啟動

```bash
source .venv/bin/activate
python -m src.gui.app   # GUI 模式（推薦）
python -m src.main      # 終端機模式
```

## 專案結構

```text
project/
├── src/
│   ├── gui/
│   │   ├── app.py                   # GUI 主介面（Tkinter）
│   │   └── schedule_popup_helper.py # 排程與規則面板
│   ├── core/
│   │   ├── agent.py                 # 核心指令處理流程
│   │   ├── scheduler.py             # 排程管理
│   │   ├── scheduler_runtime.py     # 排程背景執行
│   │   ├── memory_agent.py          # 記憶與規則管理
│   │   ├── state_manager.py         # 裝置狀態管理
│   │   └── parser/
│   │       ├── fastpath_parser.py   # 規則引擎（本地快速解析）
│   │       ├── gemini_parser.py     # Gemini API 解析
│   │       └── schedule_parser.py  # 排程指令解析
│   ├── devices/
│   │   ├── device_controller.py     # GPIO 統一控制介面
│   │   ├── hardware_led.py          # LED 控制
│   │   ├── hardware_fan.py          # 風扇控制
│   │   ├── hardware_7seg.py         # 七段顯示器
│   │   └── hardware_dht11.py        # 溫濕度感測
│   ├── audio/
│   │   └── speech_processor.py     # 語音錄製與辨識
│   ├── services/
│   │   ├── gui_command_service.py   # GUI 指令執行服務
│   │   └── gui_state_service.py    # GUI 狀態顯示服務
│   └── utils/
│       ├── config.py               # 全域設定
│       ├── tts.py                  # Piper TTS 封裝
│       └── whisper_local.py        # faster-whisper 封裝
├── data/
│   ├── models/                     # TTS 模型（.onnx）與喚醒詞模型
│   ├── memory/                     # 排程、規則、短期/長期記憶
│   └── audio/                      # 提示音效
├── scripts/
│   └── setup.sh                    # 安裝腳本
├── requirements/
│   ├── base.txt                    # 核心依賴
│   ├── pi.txt                      # 樹莓派硬體依賴
│   ├── desktop.txt                 # 桌面開發依賴
│   └── dev.txt                     # 測試與開發工具
└── .env                            # 環境變數（不納入版本控制）
```

## GUI 介面說明

- **左側**：對話紀錄、狀態顯示、文字輸入欄
- **右側**：
  - 快捷操作（全部開燈、全部關燈、重置狀態）
  - **家具狀態**：即時顯示溫度、風扇、各區域燈光狀態
  - **使用者習慣**：管理已學習的自訂詞語規則
  - **排程 Queue**：查看、新增、刪除、啟用／停用排程
- 左上角 `←` `→` 按鈕可在頁面間返回與前進
- 右上角語言切換（中文 / English）

## 指令範例

### 裝置控制

```
開廚房的燈
關風扇
溫度調到 26 度
全部關掉
```

### 排程設定

```
明天早上 8 點開客廳的燈
每天晚上 11 點關全部的燈
5 分鐘後關風扇
in 10 minutes turn off all lights
```

### 自訂規則學習

```
當我說「睡覺了」，代表全部關燈、關風扇
from now on "good night" means turn off all lights and fan
```

### 查詢與管理

```
查看排程
刪除排程 ab12cd34
我的使用者習慣
```

## 環境變數說明

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `GEMINI_API_KEY` | Gemini API 金鑰 | 必填 |
| `RUNTIME_MODE` | 執行模式（`hardware` / `desktop`） | `hardware` |
| `SPEECH_ENABLED` | 啟用語音輸入 | `1` |
| `WAKEWORD_ENABLED` | 啟用喚醒詞偵測 | `1` |
| `TTS_ENABLED` | 啟用語音輸出 | `1` |
| `DHT11_ENABLED` | 啟用 DHT11 感測器 | `1` |
| `DEVICE_PORT` | 麥克風 ALSA 裝置 | `plughw:3,0` |
| `TTS_DEVICE` | 喇叭 ALSA 裝置 | `default` |
| `VOICE_ONLY_MODE` | 純語音模式（隱藏文字輸入） | `1` |
| `SHOW_DEBUG_TEXT_INPUT` | 顯示 Debug 文字輸入 | `0` |

## 打包成桌面執行檔（樹莓派）

```bash
source .venv/bin/activate
pip install pyinstaller
pyinstaller --onefile --windowed \
  --add-data "data:data" \
  --add-data "piper:piper" \
  --name SmartHome \
  src/gui/app.py

cp dist/SmartHome ~/Desktop/SmartHome
chmod +x ~/Desktop/SmartHome
```

## 常見問題

**Q: 喇叭沒有聲音**
```bash
aplay -l   # 確認音訊裝置編號
# 在 .env 設定 TTS_DEVICE=plughw:X,0（X 為對應卡號）
```

**Q: 麥克風無法錄音**
```bash
arecord -l   # 確認麥克風裝置編號
# 在 .env 設定 DEVICE_PORT=plughw:X,0
```

**Q: Gemini API 額度不足**

FastPath 本地規則引擎仍可處理常見指令（開關燈、風扇、溫度設定），不影響基本功能使用。

**Q: 英文 TTS 模型找不到**
```bash
wget -P data/models/ \
  https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx
```
