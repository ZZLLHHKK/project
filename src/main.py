import os


def main() -> None:
    # 薄入口：固定桌面模式，核心流程委派到 true_main。
    os.environ["RUNTIME_MODE"] = "desktop"
    os.environ["DHT11_ENABLED"] = "0"
    os.environ["SPEECH_ENABLED"] = "0"
    os.environ["WAKEWORD_ENABLED"] = "0"
    os.environ["TTS_ENABLED"] = "0"

    from src.true_main import main as run_core

    run_core()

if __name__ == "__main__":
    main()