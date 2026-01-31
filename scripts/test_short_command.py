from src.nodes.short_command import match_short_command
# 測試句子判斷動作

test_sentences = [
    # 燈 - 正確與輕微變形
    "開燈",
    "關燈",
    "打開燈",
    "關掉燈",
    "燈開",
    "燈關",
    "開燈啦",
    "開燈嗎",
    "把燈打開",
    "燈要開",

    # 燈 - 常見諧音誤認
    "開當",
    "開鄧",
    "開登",
    "開堂",
    "開黨",
    "關當",
    "關鄧",
    "關登",
    "關堂",
    "關黨",
    "開燈啊",
    "關燈啊",
    "turn on like",
    "turn off like",
    "turn on right",
    "light on",
    "lights on",
    "lights off",

    # 風扇 - 正確與變形
    "開風扇",
    "關風扇",
    "開電扇",
    "關電扇",
    "開電風扇",
    "關電風扇",
    "fan on",
    "fan off",
    "turn on fan",

    # 風扇 - 誤認
    "開電山",
    "開電三",
    "開電善",
    "開店扇",
    "開電風山",
    "開電豐扇",
    "關電山",
    "關電三",
    "關電善",
    "關店扇",
    "turn on fans",
    "turn off van",
    "fun on",

    # 冷氣 - 正確與變形
    "開冷氣",
    "關冷氣",
    "開空調",
    "關空調",
    "冷氣 25 度",
    "冷氣調 26 度",
    "調冷氣 24 度",
    "set ac 27",
    "ac on",
    "ac off",

    # 冷氣 - 誤認與溫度變形
    "開冷起",
    "開冷七",
    "開冷期",
    "開冷汽",
    "關冷起",
    "關冷七",
    "開空掉",
    "關空掉",
    "冷起 25 度",
    "冷氣調 2 5 度",
    "冷氣 25 渡",
    "冷氣調 16 都",
    "把冷氣調到 26 度",
    "set a c to 25",
    "set ace to 26",
    "lower ac",
    "lower a c",

    # 明顯無關或太模糊（應回 None）
    "今天天氣很好",
    "你好嗎",
    "燈要亮一點",
    "冷氣要涼一點",
    "我很熱",
    "開門",
    "關窗戶",
    "播放音樂",
    "幾點了",
    "誰在說話"
]

for s in test_sentences:
    result = match_short_command(s)
    print(f"輸入: {s} → 輸出: {result}")