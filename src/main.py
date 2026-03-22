import os


def main() -> None:
    # 薄入口：固定桌面模式，核心流程委派到 true_main。
    os.environ["RUNTIME_MODE"] = "desktop"
    # Desktop 預設保留語音互動，若裝置不可用會在 true_main 自動降級成鍵盤輸入。
    os.environ.setdefault("DHT11_ENABLED", "0")
    os.environ.setdefault("SPEECH_ENABLED", "1")
    os.environ.setdefault("WAKEWORD_ENABLED", "1")
    os.environ.setdefault("TTS_ENABLED", "1")

    from src.true_main import main as run_core

    run_core()

if __name__ == "__main__":
    main()