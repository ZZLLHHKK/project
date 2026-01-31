# 套件說明

### langgraph 和 gemini 相關套件

- langgraph  
  用於建立具狀態的 LLM 工作流程（graph-based agents）

- langchain-core  
  LangChain 的核心抽象與基礎元件

- langchain-google-genai  
  串接 Google Gemini 模型

- google-generativeai  
  Google 官方 Generative AI SDK

- python-dotenv  
  從 `.env` 載入 API Key 與環境變數

- typing-extensions  
  補齊較新 Python typing 功能（向下相容）

### 其他

- sounddevice  
  即時錄音與音訊輸入

- scipy  
  音訊處理與數值運算

- python-Levenshtein  
  文本相似度計算（2026/1/26 新增）

### ipynb相關套件

- jupyter
  Jupyter Notebook / JupyterLab 主程式（如果還沒裝 Jupyter 環境

- ipython
  IPython kernel，提供 display()、Image() 等顯示功能

- langgraph-checkpoint
  LangGraph 的 checkpoint 支援（有些版本需要

- langgraph-checkpoint-sqlite
  簡單的本地 checkpoint 儲存（可選，但很多範例會用到）

- pygraphviz 
  (前置作業)
  
  先跳出.venv，執行:

  ```
  sudo apt update
  sudo apt install -y graphviz graphviz-dev pkg-config
  ```
  再啟用:
  ```
  source .venv/bin/activate
  pip uninstall pygraphviz -y
  pip install pygraphviz --no-cache-dir # 避免用到舊快取
  python -c "import pygraphviz; print('pygraphviz OK')" # 確認安裝成功
  ```
  用來產生圖形結構（draw_mermaid_png 內部依賴 graphviz

- pillow
  Python Imaging Library，用來處理 PNG 圖片顯示