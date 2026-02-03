# 樹莓派本地語音家電控制系統

一個完全離線、本地處理的語音控制家電專案，使用樹莓派 + Whisper.cpp + LangGraph + Gemini LLM，支援中英混說、多動作指令、使用者習慣記憶，強調隱私保護與高度自訂。

## 專案目前功能

- 全本地語音辨識（Whisper.cpp），無需上網，不傳資料
- 支援中英混說 + 常見誤認容錯
- 短指令快速匹配 + 多動作拆分
- GPIO 控制真實家電（燈、風扇、冷氣）
- 開源、可自訂指令與硬體

## 專案未來功能新增

- 未來整合 RAG（語意摘要）與使用者習慣學習

## 系統架構

- 錄音 → Whisper.cpp 轉錄 → input.txt
- classify → 明確指令（regex + 關鍵字）或 模糊指令 （丟給 LLM）
- short → 寫 output.txt + GPIO 執行
- llm_needed → Gemini 分析語意（未來加 RAG）
- 狀態管理：LangGraph 圖形流程 + 記憶 history

## 資料夾結構

```bash=
project/                                   # 專案根目錄（建議 git repo）
├── .venv/                                 # 虛擬環境（隱藏資料夾，pip install 都在這裡）
│   ├── bin/                               # python、pip、activate 等
│   ├── lib/
│   └── ... (其他 venv 內容)
│
├── data/                                  # 運行時產生/暫存資料
│   ├── recordings/                        # 每次錄音的 .wav 檔（可設定自動刪除）
│   ├── input.txt                          # Whisper 最新轉錄文字（覆蓋或 append）
│   ├── output.txt                         # 最終解析出的指令（文字或 JSON）
│   ├── memory.txt                         # 使用者習慣之記憶功能
│   ├── action.txt                         # 動作格式輸出
│   ├── history.jsonl                      # 動作歷史紀錄
│   ├── reply.txt                          # llm 回覆文字
│   └── logs/                              # 日誌檔（可選，.txt 或 .jsonl）
│
├── scripts/                               # 一次性或測試腳本（非主程式）
│   ├── setup.sh                           # 安裝依賴、編譯 whisper.cpp 的腳本
│   ├── test_stt.py                        # 單獨測試轉錄
│   ├── test_record.py                     # 單獨測試錄音
│   ├── test_short_command.py              # 單獨測試指令轉json
│   └── test_graph.py                      # 單獨測試 LangGraph 流程
│
├── src/                                   # 所有 Python 主要程式碼
│   ├── __init__.py                        # 主程式初始化
│   ├── main.py                            # 程式進入點（啟動 graph、持續監聽錄音 loop）
│   ├── graph.py                           # LangGraph 主流程（nodes + edges + conditional）
│   ├── nodes/                             # 每個 LangGraph node 獨立檔案
│   │   ├── classify.py                    # 判斷明確/模糊指令 (可略)
│   │   ├── short_command.py               # Regex明確指令 → 寫 output.txt (可略)
│   │   └── langgraph_split_files/         # GPIO主邏輯結點
│   │       ├── action_schema.py           # 定義統一的 action 格式（SET_TEMP / LED / FAN）        
│   │       ├── hardware_7seg.py           # 七段顯示器執行器
│   │       ├── hardware_fan.py            # 風扇執行器
│   │       ├── hardware_led.py            # LED 執行器
│   │       ├── parser_fastpath.py         # 不靠 Gemini 的快速解析
│   │       ├── parser_gemini.py           # 用 Gemini API 處理模糊語意，把「人話」轉成 actions（JSON list）
│   │       └── validator.py               # actions 的安全/格式檢查層
│   │
│   └── utils/                             # 共用工具函式
│       ├── audio.py                       # 錄音、存檔、刪除暫存 wav
│       ├── whisper_local.py               # whisper.cpp 呼叫封裝（相對路徑）
│       ├── file_io.py                     # 讀寫 input.txt / output.txt / log
│       └── config.py                      # 集中設定路徑（模型名、語言、pin 對應、錄音秒數等）
│
├── whisper.cpp/                           # whisper.cpp 完整資料夾（可攜式，不拆分）
│   ├── main                               # 編譯出的主執行檔（或 whisper-cli 等）
│   ├── models/                            # 模型檔緊跟在 whisper.cpp 裡
│   │   ├── ggml-tiny.bin                  # 建議從 tiny/base 開始
│   │   ├── ggml-base.bin
│   │   └── ggml-small.bin                 # 效能允許再用
│   └── ...                                # 其他 whisper.cpp 原始碼 / lib 等（可忽略細節）
│
├── .env                                   # 環境變數（GEMINI_API_KEY 等）
├── .gitignore                             # 忽略 venv、data/recordings、.env、模型大檔等
├── requirements.txt                       # 套件清單（langgraph、langchain-google-genai 等）
├── graph_visual.ipynb                     # 觀察langgraph的模樣
├── description/                           # 程式細節與目前問題說明
│   ├── whisper.md                         # whisper.cpp的下載流程
│   ├── jupyter.md                         # 使用.ipynb的前置作業 
│   ├── bug.md                             # 目前程式的問題
│   ├── detail.md                          # 程式細節(不同樹莓派機器須注意)
│   └── INSTALL.md                         # 套件說明 
└── README.md                              # 專案說明、安裝步驟、硬體需求、啟動方式
```

## 安裝與啟動（樹莓派環境）

### 需求

- Raspberry Pi 4
- Raspberry Pi OS
- Raspberry Pi 專用充電插座 (提供穩定電供)
- 麥克風（USB 或內建）
- GPIO 接的家電（燈、風扇、冷氣等）

### 推薦安裝方式（一鍵安裝）

使用提供的安裝腳本進行完整設定：

```bash
git clone https://github.com/ZZLLHHKK/project.git
cd 你的專案
bash scripts/setup.sh
```

腳本會自動處理所有依賴安裝、whisper.cpp 下載編譯、Python 套件安裝等。詳見 [setup.sh](scripts/setup.sh)。

### 手動安裝步驟（備用）

如果需要手動安裝，請跟隨以下步驟：

1. Clone 專案

   ```bash
   git clone https://github.com/ZZLLHHKK/project.git
   cd 你的專案
   ```

2. 建立虛擬環境

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. 安裝 Python 套件

   請先參考 [下載前置作業](description/INSTALL.md)

   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. 安裝系統依賴

   ```bash
   sudo apt update
   sudo apt install -y python3-dev libatlas-base-dev libopenblas-dev libsndfile1-dev portaudio19-dev libportaudio2 alsa-utils gpiozero
   ```

5. 編譯 whisper.cpp

   詳見 [whisper.cpp使用筆記](description/whisper.md)

6. 設定環境變數

   建立 `.env` 檔：

   ```bash
   GEMINI_API_KEY=你的金鑰
   ```

7. 啟動程式

   ```bash
   source .venv/bin/activate
   python -m src.main
   ```

## 其他

詳情請閱讀 `description` 資料夾的 markdown 檔案