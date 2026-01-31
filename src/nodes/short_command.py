# src/nodes/short_command.py

SHORT_COMMANDS = {
    # 開/關燈（中英 + 常見誤認）
    "開燈":          {"action": "turn_on",  "device": "light",  "value": None},
    "關燈":          {"action": "turn_off", "device": "light",  "value": None},
    "打開燈":        {"action": "turn_on",  "device": "light",  "value": None},
    "關掉燈":        {"action": "turn_off", "device": "light",  "value": None},
    "燈開":          {"action": "turn_on",  "device": "light",  "value": None},
    "燈關":          {"action": "turn_off", "device": "light",  "value": None},
    "開當":          {"action": "turn_on",  "device": "light",  "value": None},
    "開鄧":          {"action": "turn_on",  "device": "light",  "value": None},
    "開登":          {"action": "turn_on",  "device": "light",  "value": None},
    "開堂":          {"action": "turn_on",  "device": "light",  "value": None},
    "開黨":          {"action": "turn_on",  "device": "light",  "value": None},
    "開燈嗎":        {"action": "turn_on",  "device": "light",  "value": None},
    "開燈啦":        {"action": "turn_on",  "device": "light",  "value": None},
    "關當":          {"action": "turn_off", "device": "light",  "value": None},
    "關鄧":          {"action": "turn_off", "device": "light",  "value": None},
    "關登":          {"action": "turn_off", "device": "light",  "value": None},
    "關堂":          {"action": "turn_off", "device": "light",  "value": None},
    "關黨":          {"action": "turn_off", "device": "light",  "value": None},
    "關燈啊":        {"action": "turn_off", "device": "light",  "value": None},
    "turn on light": {"action": "turn_on",  "device": "light",  "value": None},
    "turn off light":{"action": "turn_off", "device": "light",  "value": None},
    "light on":      {"action": "turn_on",  "device": "light",  "value": None},
    "light off":     {"action": "turn_off", "device": "light",  "value": None},
    "turn on like":  {"action": "turn_on",  "device": "light",  "value": None},
    "turn off like": {"action": "turn_off", "device": "light",  "value": None},
    "turn on right": {"action": "turn_on",  "device": "light",  "value": None},
    "turn off right":{"action": "turn_off", "device": "light",  "value": None},
    "lights on":     {"action": "turn_on",  "device": "light",  "value": None},
    "lights off":    {"action": "turn_off", "device": "light",  "value": None},

    # 風扇（中英 + 常見誤認）
    "開風扇":        {"action": "turn_on",  "device": "fan",    "value": None},
    "關風扇":        {"action": "turn_off", "device": "fan",    "value": None},
    "開電扇":        {"action": "turn_on",  "device": "fan",    "value": None},
    "關電扇":        {"action": "turn_off", "device": "fan",    "value": None},
    "開店扇":        {"action": "turn_on",  "device": "fan",    "value": None},
    "開電山":        {"action": "turn_on",  "device": "fan",    "value": None},
    "開電三":        {"action": "turn_on",  "device": "fan",    "value": None},
    "開電善":        {"action": "turn_on",  "device": "fan",    "value": None},
    "開電扇嗎":      {"action": "turn_on",  "device": "fan",    "value": None},
    "關電山":        {"action": "turn_off", "device": "fan",    "value": None},
    "關電三":        {"action": "turn_off", "device": "fan",    "value": None},
    "關電善":        {"action": "turn_off", "device": "fan",    "value": None},
    "關店扇":        {"action": "turn_off", "device": "fan",    "value": None},
    "開電風扇":      {"action": "turn_on",  "device": "fan",    "value": None},
    "關電風扇":      {"action": "turn_off", "device": "fan",    "value": None},
    "開電風山":      {"action": "turn_on",  "device": "fan",    "value": None},
    "開電豐扇":      {"action": "turn_on",  "device": "fan",    "value": None},
    "開電風三":      {"action": "turn_on",  "device": "fan",    "value": None},
    "開電風善":      {"action": "turn_on",  "device": "fan",    "value": None},
    "開電風扇啊":    {"action": "turn_on",  "device": "fan",    "value": None},
    "關電風山":      {"action": "turn_off", "device": "fan",    "value": None},
    "關電豐扇":      {"action": "turn_off", "device": "fan",    "value": None},
    "關電風三":      {"action": "turn_off", "device": "fan",    "value": None},
    "關電風善":      {"action": "turn_off", "device": "fan",    "value": None},
    "關電風扇吧":    {"action": "turn_off", "device": "fan",    "value": None},
    "fan on":        {"action": "turn_on",  "device": "fan",    "value": None},
    "fan off":       {"action": "turn_off", "device": "fan",    "value": None},
    "turn on fan":   {"action": "turn_on",  "device": "fan",    "value": None},
    "turn off fan":  {"action": "turn_off", "device": "fan",    "value": None},
    "turn on fans":  {"action": "turn_on",  "device": "fan",    "value": None},
    "turn off fans": {"action": "turn_off", "device": "fan",    "value": None},
    "van on":        {"action": "turn_on",  "device": "fan",    "value": None},
    "van off":       {"action": "turn_off", "device": "fan",    "value": None},
    "fun on":        {"action": "turn_on",  "device": "fan",    "value": None},
    "fun off":       {"action": "turn_off", "device": "fan",    "value": None},

    # 冷氣（中英 + 常見誤認）
    "開冷氣":        {"action": "turn_on",  "device": "ac",     "value": None},
    "關冷氣":        {"action": "turn_off", "device": "ac",     "value": None},
    "開空調":        {"action": "turn_on",  "device": "ac",     "value": None},
    "關空調":        {"action": "turn_off", "device": "ac",     "value": None},
    "開冷起":        {"action": "turn_on",  "device": "ac",     "value": None},
    "開冷七":        {"action": "turn_on",  "device": "ac",     "value": None},
    "開冷期":        {"action": "turn_on",  "device": "ac",     "value": None},
    "開冷汽":        {"action": "turn_on",  "device": "ac",     "value": None},
    "開冷氣嗎":      {"action": "turn_on",  "device": "ac",     "value": None},
    "關冷起":        {"action": "turn_off", "device": "ac",     "value": None},
    "關冷七":        {"action": "turn_off", "device": "ac",     "value": None},
    "關冷期":        {"action": "turn_off", "device": "ac",     "value": None},
    "關冷汽":        {"action": "turn_off", "device": "ac",     "value": None},
    "關冷氣啊":      {"action": "turn_off", "device": "ac",     "value": None},
    "開空掉":        {"action": "turn_on",  "device": "ac",     "value": None},
    "開空調嗎":      {"action": "turn_on",  "device": "ac",     "value": None},
    "開空調啊":      {"action": "turn_on",  "device": "ac",     "value": None},
    "關空掉":        {"action": "turn_off", "device": "ac",     "value": None},
    "關空調吧":      {"action": "turn_off", "device": "ac",     "value": None},
    "關空調啊":      {"action": "turn_off", "device": "ac",     "value": None},
    "ac on":         {"action": "turn_on",  "device": "ac",     "value": None},
    "ac off":        {"action": "turn_off", "device": "ac",     "value": None},
    "turn on ac":    {"action": "turn_on",  "device": "ac",     "value": None},
    "turn off ac":   {"action": "turn_off", "device": "ac",     "value": None},
    "a c on":        {"action": "turn_on",  "device": "ac",     "value": None},
    "ace on":        {"action": "turn_on",  "device": "ac",     "value": None},
    "as on":         {"action": "turn_on",  "device": "ac",     "value": None},
    "a c off":       {"action": "turn_off", "device": "ac",     "value": None},
    "ace off":       {"action": "turn_off", "device": "ac",     "value": None},
    "as off":        {"action": "turn_off", "device": "ac",     "value": None},

    # 調整冷氣溫度（中英 + 常見誤認）
    "冷氣 25 度":    {"action": "set_temp", "device": "ac",     "value": 25},
    "冷氣 26 度":    {"action": "set_temp", "device": "ac",     "value": 26},
    "冷氣 24 度":    {"action": "set_temp", "device": "ac",     "value": 24},
    "冷氣 27 度":    {"action": "set_temp", "device": "ac",     "value": 27},
    "冷氣調 25 度":  {"action": "set_temp", "device": "ac",     "value": 25},
    "調冷氣 25 度":  {"action": "set_temp", "device": "ac",     "value": 25},
    "冷氣 25":       {"action": "set_temp", "device": "ac",     "value": 25},
    "冷起 25 度":    {"action": "set_temp", "device": "ac",     "value": 25},
    "冷氣調 2 5 度": {"action": "set_temp", "device": "ac",     "value": 25},
    "調冷氣 2 5 度": {"action": "set_temp", "device": "ac",     "value": 25},
    "冷氣調 25 渡":  {"action": "set_temp", "device": "ac",     "value": 25},
    "冷氣調 25 都":  {"action": "set_temp", "device": "ac",     "value": 25},
    "把冷氣調到 25 度": {"action": "set_temp", "device": "ac",     "value": 25},
    "把冷起調到 25 度": {"action": "set_temp", "device": "ac",     "value": 25},
    "把冷氣調到 25 渡": {"action": "set_temp", "device": "ac",     "value": 25},
    "把冷氣調到 25 都啊": {"action": "set_temp", "device": "ac",     "value": 25},
    "冷氣低一點":    {"action": "lower_temp", "device": "ac",   "value": None},
    "冷氣高一點":    {"action": "higher_temp", "device": "ac",  "value": None},
    "set ac 25":     {"action": "set_temp", "device": "ac",     "value": 25},
    "set ac 26":     {"action": "set_temp", "device": "ac",     "value": 26},
    "set a c to 25": {"action": "set_temp", "device": "ac",     "value": 25},
    "set ace to 25": {"action": "set_temp", "device": "ac",     "value": 25},
    "set as to 25":  {"action": "set_temp", "device": "ac",     "value": 25},
    "ac 25 degrees": {"action": "set_temp", "device": "ac",     "value": 25},
    "a c 25 degrees": {"action": "set_temp", "device": "ac",    "value": 25},
    "ace 25 degrees": {"action": "set_temp", "device": "ac",    "value": 25},
    "set air conditioner to 25": {"action": "set_temp", "device": "ac", "value": 25},
    "set air conditioner to 2 5": {"action": "set_temp", "device": "ac", "value": 25},
    "lower ac":      {"action": "lower_temp", "device": "ac",   "value": None},
    "lower a c":     {"action": "lower_temp", "device": "ac",   "value": None},
    "lower ace":     {"action": "lower_temp", "device": "ac",   "value": None},
}

def clean_text(text: str) -> str:
    """清理常見 Whisper 誤認字"""
    text = text.strip().lower()
    replacements = {
        "當": "燈", "鄧": "燈", "登": "燈", "堂": "燈", "黨": "燈", "當": "燈",
        "起": "氣", "七": "氣", "期": "氣", "汽": "氣", "起": "氣",
        "掉": "調", "到": "調",
        "山": "扇", "三": "扇", "善": "扇",
        "豐": "風", "風": "風",  # 風扇的風
        "like": "light", "right": "light", "van": "fan", "fun": "fan",
        "a c": "ac", "ace": "ac", "as": "ac",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text
    
def match_short_command(text: str) -> dict | None:
    """
    回傳匹配到的指令字典，或 None(沒匹配)
    """
    text = clean_text(text.strip().lower())

    # 先排除明顯否定句
    if any(word in text for word in ["不", "不要", "別", "不是"]):
        return None

    # 1. 完全匹配（最高優先）
    if text in SHORT_COMMANDS:
        return SHORT_COMMANDS[text]

    # 2. 溫度相關 regex（優先抓數字）
    import re
    temp_patterns = [
        r"(冷氣|空調|ac)\D*(\d{2})\D*(度|度數)?",
        r"調\s*(冷氣|空調)\s*到?\s*(\d{2})",
        r"set\s*(ac|air conditioner)\s*to\s*(\d{2})",
        r"冷氣\s*(\d+)\s*度",
        r"set ac (\d+)",
    ]
    for pattern in temp_patterns:
        match = re.search(pattern, text)
        if match:
            # 取最後一個數字 group
            for group in reversed(match.groups()):
                if group and group.isdigit():
                    temp = int(group)
                    if 16 <= temp <= 30:
                        return {"action": "set_temp", "device": "ac", "value": temp}
                    break

    # 3. 關鍵字組合（燈、風扇、冷氣開關） 避免句子太鬆散
    if "開" in text and "燈" in text:
        return {"action": "turn_on", "device": "light", "value": None}
    if "關" in text and "燈" in text:
        return {"action": "turn_off", "device": "light", "value": None}

    if "開" in text and any(fan_word in text for fan_word in ["風扇", "電扇", "電風扇", "fan"]):
        return {"action": "turn_on", "device": "fan", "value": None}
    if "關" in text and any(fan_word in text for fan_word in ["風扇", "電扇", "電風扇", "fan"]):
        return {"action": "turn_off", "device": "fan", "value": None}

    if "開" in text and any(ac_word in text for ac_word in ["冷氣", "空調", "ac"]):
        return {"action": "turn_on", "device": "ac", "value": None}
    if "關" in text and any(ac_word in text for ac_word in ["冷氣", "空調", "ac"]):
        return {"action": "turn_off", "device": "ac", "value": None}

    # 4. 溫度升降（低/高一點）
    if "低一點" in text and any(ac_word in text for ac_word in ["冷氣", "空調", "ac"]):
        return {"action": "lower_temp", "device": "ac", "value": None}
    if "高一點" in text and any(ac_word in text for ac_word in ["冷氣", "空調", "ac"]):
        return {"action": "higher_temp", "device": "ac", "value": None}

    # 沒匹配到
    return None