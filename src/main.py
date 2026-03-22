import os


def main() -> None:
    # 薄入口：固定桌面模式，核心流程委派到 true_main。
    os.environ["RUNTIME_MODE"] = "desktop"
    # Desktop 預設：鍵盤喚醒詞 + 語音命令 + Piper TTS。
    os.environ.setdefault("DHT11_ENABLED", "0")
    os.environ.setdefault("SPEECH_ENABLED", "1")
    os.environ.setdefault("WAKEWORD_ENABLED", "0")
    os.environ.setdefault("TTS_ENABLED", "1")

    from src.true_main import main as run_core

    run_core()

if __name__ == "__main__":
    main()