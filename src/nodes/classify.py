# 略

from src.nodes.short_command import match_short_command
import re

def split_action(text: str) -> list[str]:
    text = text.strip()
    text = re.sub(r'[，；,;]', ' ', text)  # 標點轉空格
    text = ' '.join(text.split())  # 合併空格

    # 先試用連接詞拆分
    delimiters = r'\s*(並|和|然後|再|，|；|;|and|then|also|plus|next|after|or)\s*'   
    parts = re.split(delimiters, text)
    actions = [p.strip() for p in parts if p.strip() and p not in ['並', '和', '然後', '再', '，', '；', ';']]

    # 如果只拆出一個，試用動作關鍵字拆分
    if len(actions) <= 1:
        # 用動作關鍵字拆
        pattern = r'([開關調把讓將turnset][^開關調把讓將turnset]*)'
        actions = [m.group(0).strip() for m in re.finditer(pattern, text) if m.group(0).strip()]

    print("拆分結果:", actions)
    return actions

def classify_input(text: str) -> dict:
    """
    簡單二分：
    - 明確匹配 short_command → short
    - 其他全部 → llm(之後會丟給 Gemini 分析)
    """
    actions = split_action(text)
    
    matched_commands = []
    for sub in actions:
        cmd = match_short_command(sub)
        if cmd:
            matched_commands.append(cmd)
    
    if matched_commands:
        return {
            "type": "short",
            "commands": matched_commands,  # list of dict
            "original_text": text
        }
    else:
        return {
            "type": "llm_needed",
            "original_text": text
        }