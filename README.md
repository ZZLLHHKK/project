# 樹莓派本地語音家電控制系統

一個完全離線、本地處理的語音控制家電專案，使用樹莓派 + Whisper.cpp + LangGraph + Gemini LLM，支援中英混說、多動作指令、使用者習慣記憶，強調隱私保護與高度自訂。

## 專案目前功能

- 全本地語音辨識（Whisper.cpp），無需上網，不傳資料
- 支援中英混說 + 常見誤認容錯
- 短指令快速匹配 + 多動作拆分

## 專案未來功能新增

- 未來整合 RAG（語意摘要）與使用者習慣學習
- GPIO 控制真實家電（燈、風扇、冷氣）
- 開源、可自訂指令與硬體

## 系統架構

- 錄音 → Whisper.cpp 轉錄 → input.txt
- classify → 明確指令（regex + 關鍵字）或 模糊指令 （丟給 LLM）
- short → 寫 output.txt + GPIO 執行
- llm_needed → Gemini 分析語意（未來加 RAG）
- 狀態管理：LangGraph 圖形流程 + 記憶 history

## 資料夾結構

```bash=
project/                          # 專案根目錄（建議 git repo）
├── .venv/                                 # 虛擬環境（隱藏資料夾，pip install 都在這裡）
│   ├── bin/                               # python、pip、activate 等
│   ├── lib/
│   └── ... (其他 venv 內容)
├── data/                                  # 運行時產生/暫存資料
│   ├── recordings/                        # 每次錄音的 .wav 檔（可設定自動刪除）
│   ├── input.txt                          # Whisper 最新轉錄文字（覆蓋或 append）
│   ├── output.txt                         # 最終解析出的指令（文字或 JSON）
│   └── logs/                              # 日誌檔（可選，.txt 或 .jsonl）
├── scripts/                               # 一次性或測試腳本（非主程式）
│   ├── setup.sh                           # 安裝依賴、編譯 whisper.cpp 的腳本
│   ├── test_stt.py                        # 單獨測試轉錄
│   ├── test_record.py                     # 單獨測試錄音
│   ├── test_short_command.py              # 單獨測試指令轉json
│   └── test_graph.py                      # 單獨測試 LangGraph 流程
├── src/                                   # 所有 Python 主要程式碼
│   ├── __init__.py
│   ├── main.py                            # 程式進入點（啟動 graph、持續監聽錄音 loop）
│   ├── graph.py                           # LangGraph 主流程（nodes + edges + conditional）
│   ├── nodes/                             # 每個 LangGraph node 獨立檔案
│   │   ├── __init__.py
│   │   ├── stt.py                         # 錄音 + whisper → 寫 input.txt
│   │   ├── classify.py                    # 判斷明確/模糊指令
│   │   ├── short_command.py               # Regex明確指令 → 寫 output.txt
│   │   ├── intent.py                      # Gemini LLM 解析長指令 → output.txt 或重錄
│   │   ├── execute.py                     # 讀 output.txt → 控制 GPIO / 回報錯誤
│   │   └── clarifier.py                   # （可選）主動問澄清的 node
│   └── utils/                             # 共用工具函式（方案 1：GPIO 放這裡）
│       ├── __init__.py                    # （可選）
│       ├── audio.py                       # 錄音、存檔、刪除暫存 wav
│       ├── whisper_local.py               # whisper.cpp 呼叫封裝（相對路徑）
│       ├── file_io.py                     # 讀寫 input.txt / output.txt / log
│       ├── gpio.py                        # GPIO 控制（燈、風扇、冷氣等）
│       └── config.py                      # 集中設定路徑（模型名、語言、pin 對應、錄音秒數等）
├── tests/                                 # 單元測試資料夾（目前可空，未來擴充）
│   └── __init__.py                        # （可選）
├── whisper.cpp/                           # whisper.cpp 完整資料夾（可攜式，不拆分）
│   ├── main                               # 編譯出的主執行檔（或 whisper-cli 等）
│   ├── models/                            # 模型檔緊跟在 whisper.cpp 裡
│   │   ├── ggml-tiny.bin                  # 建議從 tiny/base 開始
│   │   ├── ggml-base.bin
│   │   └── ggml-small.bin                 # 效能允許再用
│   └── ...                                # 其他 whisper.cpp 原始碼 / lib 等（可忽略細節）
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

### 步驟

1. Clone 專案

   ```bash
   git clone https://github.com/你的帳號/你的專案.git
   cd 你的專案
   ```

2. 建立虛擬環境 (必要)

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate # 啟用虛擬環境，看到(.venv)代表成功啟用
   ```

3. 安裝 Python 套件

   請先看 [下載前置作業](description/INSTALL.md) 模組出現(前置作業)需特別注意
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

4. 安裝系統依賴（音訊、GPIO 等）

   ```bash
   sudo apt update
   sudo apt install -y python3-dev libatlas-base-dev libopenblas-dev libsndfile1-dev portaudio19-dev libportaudio2 alsa-utils gpiozero
   ```

5. 編譯 whisper.cpp（如果 models 裡沒 main, 這步可略）

   詳細請看 [whisper.cpp使用筆記](description/whisper.md)

6. 設定環境變數（Gemini API key）

- 建立 `.env` 檔（不要推到 GitHub）

   ```bash
   GEMINI_API_KEY=你的金鑰
   ```

7. 啟動程式

   ```bash
   python -m src.main
   ```

## 其他

詳情請閱讀`description`的`markdown file`