from src.utils.audio import record_with_arecord, stt_pipeline
from src.utils.file_io import read_text_file, write_text_file, write_output
from src.utils.config import INPUT_TXT_PATH, OUTPUT_TXT_PATH
# 之後會加的
from src.nodes.classify import classify_input  
import time

def main():
    try:
        print("\n=== 等待指令... 請說話 ===")

        # 註解掉的錄音部分之後再開啟
        '''
        wav_path = record_with_arecord(duration=6, device="plughw:3,0")
        if not wav_path:
            time.sleep(1)
            continue
        text = stt_pipeline(duration=6, device="plughw:3,0")
        if not text:
            time.sleep(1)
            continue
        '''

        input_text = read_text_file(INPUT_TXT_PATH)
        if not input_text:
            print("input.txt 為空，等待...")
            time.sleep(1)

        print(f"\n讀到的指令:{input_text}")

        classification = classify_input(input_text)

        if classification["type"] == "short":
            print("偵測到短指令！")
            write_output(OUTPUT_TXT_PATH, classification["commands"])
            # 之後這裡處理 short_command 的結果
            # 例如：execute_short_command(classification["command"])
            # write_text_file(INPUT_TXT_PATH, "")  # 清空，避免重複
            # break  # 如果想單次結束測試
            # 或 continue  # 繼續聽下一句

        elif classification["type"] == "llm_needed":
            print("這句話需要 LLM 分析（目前先印出）")
            print(f"原始文字：{classification['original_text']}")
            # 之後這裡呼叫 LLM
            # llm_response = call_gemini(classification["original_text"])
            # print("LLM 回應：", llm_response)
            # write_text_file(INPUT_TXT_PATH, "")  # 清空
            # continue

    except KeyboardInterrupt:
        print("\n結束監聽")
    except Exception as e:
        print(f"錯誤：{e}")

if __name__ == "__main__":
    main()