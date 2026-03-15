from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


SYSTEM_RESET_KEYWORDS: tuple[str, ...] = (
    "重置",
    "清除記憶",
    "clear memory",
    "reset",
    "reset memory",
    "重設記憶",
    "清空記憶",
)


def is_system_reset_command(user_input: str) -> bool:
    text = (user_input or "").strip().lower()
    if not text:
        return False
    return any(keyword in text for keyword in SYSTEM_RESET_KEYWORDS)


class Intent(StrEnum):
    """定義使用者意圖類型，未來可擴充更多類型。"""
    DEVICE_CONTROL = "DEVICE_CONTROL"
    QUERY = "QUERY"
    CHAT = "CHAT"
    SYSTEM = "SYSTEM"
    UNKNOWN = "UNKNOWN"


class RouteType(StrEnum):
    """定義路由類型，決定系統後續流程。"""
    FAST_COMMAND = "FAST_COMMAND"
    LLM = "LLM"


@dataclass(slots=True)
class RouteDecision:
    route_type: RouteType
    intent: Intent


class IntentClassifier:
    """判斷使用者意圖，不負責流程分流。"""

    def __init__(self) -> None:
        """初始化意圖關鍵字(未來可擴充更多意圖和關鍵字以及補英文的Intent)。"""
        self.intent_keywords: dict[Intent, list[str]] = {
            Intent.SYSTEM: list(SYSTEM_RESET_KEYWORDS),

            Intent.QUERY: [
                "天氣", "時間", "幾點", "新聞",
                "查詢", "多少", "現在幾點",
                "今天日期", "星期幾", "幾月幾號",
                "氣溫", "濕度", "下雨",
                "誰是", "什麼是", "為什麼", "怎麼",
                "在哪裡", "多少錢"
            ],

            Intent.CHAT: [
                "你好", "哈囉", "謝謝", "笑話", "聊聊",
                "早安", "晚安", "嗨",
                "最近好嗎", "你是誰", "你會做什麼",
                "講個故事", "無聊", "陪我聊天"
            ],
        }

    def classify(self, user_input: str) -> Intent:
        """根據關鍵字判斷使用者意圖，預設為 UNKNOWN。"""
        text = (user_input or "").strip().lower()
        if not text:
            return Intent.UNKNOWN

        for intent, keywords in self.intent_keywords.items():
            if self.match_keyword(text, keywords):
                return intent
        return Intent.UNKNOWN

    def match_keyword(self, user_input: str, keywords: list[str]) -> bool:
        """判斷 user_input 是否包含 keywords 中的任一關鍵字，忽略大小寫。"""
        lowered = user_input.lower()
        return any(keyword.lower() in lowered for keyword in keywords)


class Router:
    """Router 只做分流，不做語意理解，也不呼叫 LLM。"""

    def __init__(self, classifier: IntentClassifier | None = None) -> None:
        """初始化 Router，接受可選的 IntentClassifier 實例，預設會創建一個新的 IntentClassifier。"""
        self.classifier = classifier or IntentClassifier()

    def route(self, user_input: str) -> RouteDecision:
        """根據 user_input 判斷 intent 和 route_type，回傳 RouteDecision。"""
        intent = self.classifier.classify(user_input)
        route_type = self.get_route_type(user_input=user_input, intent=intent)
        return RouteDecision(route_type=route_type, intent=intent)

    def is_fast_command(self, user_input: str, intent: Intent | None = None) -> bool:
        """判斷是否為快速指令，目前僅保留系統控制指令。"""
        active_intent = intent or self.classifier.classify(user_input)
        return active_intent == Intent.SYSTEM

    def get_route_type(self, user_input: str, intent: Intent | None = None) -> RouteType:
        """根據 intent 判斷 route_type，目前僅 SYSTEM 類型視為 FAST_COMMAND。"""
        if self.is_fast_command(user_input=user_input, intent=intent):
            return RouteType.FAST_COMMAND
        return RouteType.LLM

#------------- 測試區域：直接執行此檔案可快速檢查分流結果。------------
if __name__ == "__main__":
    router = Router()
    test_inputs = [
        "幫我開客廳燈",
        "現在幾點",
        "你好",
        "幫我清除記憶",
        "我想知道你會什麼",
        "",
    ]

    print("=== Router Test Area ===")
    for text in test_inputs:
        decision = router.route(text)
        print(
            f"input={text!r} | intent={decision.intent.value} | route={decision.route_type.value}"
        )

"""
Router = 快速判斷並決定流程(不負責理解語意也不呼叫LLM)
IntentClassifier = 判斷使用者意圖

流程:
text
 ↓
IntentClassifier.classify()
 ↓
intent
 ↓
Router.route()
 ↓
route_type

eg:
"幫我開客廳燈"

intent = DEVICE_CONTROL
route = FAST_COMMAND

未來 Langgraph 擴充:(conditional edge)
router_node

if intent == DEVICE_CONTROL:
    -> device_node

if intent == QUERY:
    -> llm_node
"""

"""
class Router 說明:
(1) route
輸入text eg: "把溫度調高一點"
輸出 : FAST_COMMAND, LLM, CHAT, QUERY
用途 : 決定系統下一步要怎麼做
(2) is_fast_command
判斷是否可以直接執行(parse_fastpath直接拿來用)
eg : 開燈、關燈、開風扇(不需要經過LLM)
(3) get_route_type
取得 routing 類型
eg : DEVICE_CONTROL、SMART_QUERY、CHAT、SYSTEM
未來 Langgraph 會用到
"""

"""
class IntentClassifier 說明:
(1) classify
輸入text eg: "把溫度調高一點"
輸出 : intent label eg: DEVICE_CONTROL、SMART_QUERY、CHAT、SYSTEM
用途 : 判斷使用者意圖，讓系統知道使用者想做什
(2) match_keyword
用 keyword 判斷 intent
eg : 開燈、關燈、溫度、時間、天氣。回傳 intent label
"""

"""
Intent類型
DEVICE_CONTROL : 使用者想控制設備(開燈、關燈、調高溫度等)
QUERY : 使用者想詢問資訊(天氣、時間、新聞等)
CHAT : 一般對話(閒聊、問候、笑話等)
SYSTEM : 系統指令，例如重置對話、清除記憶等(這類指令通常不會經過 LLM，而是直接由系統處理)
"""