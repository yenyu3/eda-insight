import os
import json
import re
from typing import Generator

import config
from utils.json_utils import safe_parse_json, mock_stream

try:
    import anthropic
except ImportError:
    anthropic = None

try:
    from google import genai
except ImportError:
    genai = None

# AI engine 以模組層級單例延遲初始化
_ai_engine: "AIEngine | None" = None

AI_AUDIENCE_POLICY = """
你是 VeriFlow Insight 的 EDA 分析助理。
主要讀者是 AE、PM、初階硬體工程師，以及需要快速判斷設計狀態的人。
請使用繁體中文，語氣清楚、務實、可行動。
避免過度技術術語；必要術語請用一句話補充意義。
不要重複輸入資料中已經明確列出的數字表格。
若資料不足，請明確說「目前資料不足」，不要推測。
每個文字欄位最多 2 句話。
""".strip()

JSON_OUTPUT_POLICY = """
只回傳有效 JSON，不要 markdown backtick，不要額外說明文字。
JSON 字串值內不要使用 Markdown、星號粗體、項目符號或標題語法。
如果某項資料不足，請填入空陣列、null，或用一句話說明限制。
""".strip()


class AIProviderUnavailable(RuntimeError):
    """Raised when real AI mode is requested but no provider is ready."""


def _compact_text(text: str, max_len: int = 1200) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= max_len else text[:max_len - 3] + "..."


def _dedupe_lines(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        text = str(item).strip()
        if not text:
            continue
        key = re.sub(r"\s+", " ", text).lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(text)
    return result


def _dedupe_cross_fields(summary: str, items: list[str]) -> list[str]:
    if not summary:
        return items

    summary_key = re.sub(r"\s+", " ", summary).strip().lower()
    result = []
    for item in items:
        item_key = re.sub(r"\s+", " ", str(item)).strip().lower()
        if item_key == summary_key:
            continue
        if len(item_key) > 20 and (item_key in summary_key or summary_key in item_key):
            continue
        result.append(str(item).strip())
    return result


def _normalize_ai_json(data: dict) -> dict:
    list_limits = {
        "events": 3,
        "warnings": 5,
        "limitations": 4,
        "evidence": 3,
        "next_actions": 3,
        "bottlenecks": 8,
    }
    for key, limit in list_limits.items():
        if isinstance(data.get(key), list):
            data[key] = _dedupe_lines([str(item) for item in data[key]])[:limit]

    for key, limit in {
        "summary": 220,
        "impact": 220,
        "suggestions": 220,
        "reason": 180,
    }.items():
        if isinstance(data.get(key), str):
            data[key] = _compact_text(data[key], limit)

    summary = data.get("summary")
    if isinstance(summary, str):
        for key in ("events", "warnings", "limitations", "evidence", "next_actions"):
            if isinstance(data.get(key), list):
                data[key] = _dedupe_cross_fields(summary, [str(item) for item in data[key]])

    return data


def get_ai_engine() -> "AIEngine":
    """回傳全域 AIEngine 單例（延遲初始化，避免啟動時 API key 缺失崩潰）。"""
    global _ai_engine
    if _ai_engine is None:
        _ai_engine = AIEngine()
    return _ai_engine


def reset_ai_engine() -> None:
    """重置全域單例，供測試或重新載入 provider 時使用。"""
    global _ai_engine
    _ai_engine = None


class AIEngine:
    """所有 AI 分析功能的統一入口。"""

    def __init__(self):
        self.client = None
        self.provider = config.AI_PROVIDER
        self.model = ""
        self._mock = config.USE_MOCK_AI
        self._init_error = ""

        if config.USE_MOCK_AI:
            return

        if self.provider == "gemini":
            self._init_gemini()
        else:
            self.provider = "anthropic"
            self._init_anthropic()

    @property
    def is_mock(self) -> bool:
        return self._mock

    def _init_anthropic(self) -> None:
        """初始化 Anthropic client；真實模式下失敗時保留錯誤，不回退 mock。"""
        if anthropic is None:
            self._init_error = "anthropic 套件尚未安裝。"
            return

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key or api_key in {"your-key-here", "your-anthropic-key-here"}:
            self._init_error = "ANTHROPIC_API_KEY 尚未設定。"
            return

        try:
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = config.ANTHROPIC_MODEL
        except Exception:
            self.client = None
            self._init_error = "Anthropic client 初始化失敗。"

    def _init_gemini(self) -> None:
        """初始化 Gemini client；真實模式下失敗時保留錯誤，不回退 mock。"""
        if genai is None:
            self._init_error = "google-genai 套件尚未安裝。"
            return

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key or api_key == "your-gemini-key-here":
            self._init_error = "GEMINI_API_KEY 尚未設定。"
            return

        try:
            self.client = genai.Client(api_key=api_key)
            self.model = config.GEMINI_MODEL
        except Exception:
            self.client = None
            self._init_error = "Gemini client 初始化失敗。"

    # ─── Verilog Insight ───

    def verilog_insight(self, parser_result: dict) -> Generator[str, None, None]:
        """根據 verilog_parser 輸出生成電路功能說明（串流版本）。"""
        if self._mock:
            yield from mock_stream(_mock_verilog_insight())
            return
        self._ensure_ready()

        prompt = f"""{AI_AUDIENCE_POLICY}

請根據以下 Verilog parser 結果，產生一段適合 Decision Review 的設計摘要。
請避免逐項重述所有 module/port 數字，只保留對判斷有幫助的重點。

請用以下格式回覆純文字：
結論
一句話說明這個設計主要功能。

關鍵依據
- 最多 3 點，說明你從 parser result 看到的結構重點。

資料限制
- 若 parser result 無法判斷模擬、合成或 timing，請明確說明。

Verilog parser result:
{_compact_text(json.dumps(parser_result, ensure_ascii=False), 2500)}"""
        yield from self._stream(prompt)

    # ─── Workflow Planner ───

    def workflow_planner(self, verilog_insight: str, user_goals: str) -> dict:
        """根據電路資訊與使用者目標，決定本次 pipeline 要執行哪些步驟。"""
        if self._mock:
            return _mock_workflow_plan()
        self._ensure_ready()

        prompt = f"""{JSON_OUTPUT_POLICY}

你是 EDA workflow 規劃器。請根據電路摘要與使用者目標，選擇需要執行的 pipeline steps。
允許的 steps 只有：["lint", "simulate", "synthesize", "dependency"]。

選擇原則：
- 如果使用者沒有明確排除，通常保留 simulate 與 synthesize。
- lint 適合找語法/結構風險。
- dependency 適合多 module 或需要架構觀察的設計。
- 不要選擇允許清單以外的 step。

回傳 JSON schema:
{{
  "steps": ["simulate", "synthesize"],
  "reason": "一句話說明選擇原因"
}}

電路摘要:
{_compact_text(verilog_insight, 1200)}

使用者目標:
{_compact_text(user_goals, 800)}"""

        try:
            raw = self._complete(prompt, max_tokens=256)
            data = safe_parse_json(raw)
            steps = data.get("steps", [])
            if not steps or not all(s in config.VALID_STEPS for s in steps):
                raise ValueError("AI planner 回傳格式不符合 schema。")
            reason = _compact_text(str(data.get("reason", "")), 180)
            return {"steps": steps, "reason": reason}
        except Exception as e:
            raise RuntimeError(f"AI planner failed: {e}") from e

    # ─── Log Insight ───

    def log_insight(self, log_text: str) -> dict:
        """分析 Icarus Verilog / Yosys 的 stdout log，回傳結構化摘要。"""
        if self._mock:
            return _mock_log_insight()
        self._ensure_ready()

        prompt = f"""{AI_AUDIENCE_POLICY}
{JSON_OUTPUT_POLICY}

請分析以下 EDA stage log。你的任務只限於說明工具流程狀態與 log 中明確出現的 warning/error。
不要推論設計架構風險，不要給優化建議，避免和 Risk / Bottleneck 分析重複。

回傳 JSON schema:
{{
  "summary": "2 句內說明流程是否順利，以及是否有明顯問題",
  "events": ["最多 3 個明確工具事件"],
  "warnings": ["最多 5 個明確 warning/error；沒有則空陣列"],
  "limitations": ["log 無法判斷的事項；沒有則空陣列"]
}}

Log:
{_compact_text(log_text, 2500)}"""

        try:
            return _normalize_ai_json(safe_parse_json(self._complete(prompt)))
        except Exception as e:
            return {"events": [], "warnings": [], "limitations": [], "summary": f"分析失敗：{e}"}

    # ─── Debug Advisor ───

    def debug_advisor(self, stderr_text: str, verilog_content: str) -> Generator[str, None, None]:
        """分析 EDA 工具的 stderr 錯誤訊息，串流回傳修正建議。"""
        if self._mock:
            yield from mock_stream(_mock_debug_advisor())
            return
        self._ensure_ready()

        prompt = f"""{AI_AUDIENCE_POLICY}

你是 Verilog debug advisor。請根據工具錯誤訊息與程式碼，提供可執行的修正建議。

規則：
- 如果 stderr 有明確行號，才引用行號。
- 如果沒有明確行號，不要猜行號；請指出最可能的語法模式或程式片段。
- 先說最可能原因，再給修正方式。
- 若資訊不足，請列出需要使用者補充的資料。
- 回覆請控制在 4 個短段落內。

請用以下格式：
可能原因
...

證據
...

修正建議
...

需要確認
...

錯誤訊息：
{_compact_text(stderr_text, 1200)}

Verilog 程式碼：
{_compact_text(verilog_content, 1800)}"""
        yield from self._stream(prompt)

    # ─── Risk Analyzer ───

    def risk_analyzer(self, synthesis_result: dict, waveform_stats: dict) -> dict:
        """根據合成指標與波形統計，回傳風險評分（0-10）。"""
        if self._mock:
            return _mock_risk_analysis()
        self._ensure_ready()

        prompt = f"""{AI_AUDIENCE_POLICY}
{JSON_OUTPUT_POLICY}

請根據合成指標與波形統計評估設計風險。
你的任務只限於風險分數、依據與下一步，不要重述 log 流程，也不要分析 dependency graph。

評分規則：
- 0 表示風險很低，10 表示風險很高。
- 如果 timing/slack 資料缺失，timing_risk 不要因缺失直接給高分；請在 limitations 說明資料不足。
- function_risk 應根據 simulation/waveform 是否可用判斷。
- area_risk 應根據 cell/wire/flip-flop 指標是否異常或資料是否不足判斷。

回傳 JSON schema:
{{
  "timing_risk": 0,
  "area_risk": 0,
  "function_risk": 0,
  "summary": "一句整體風險判斷",
  "evidence": ["最多 3 個實際依據"],
  "next_actions": ["最多 3 個具體下一步"],
  "confidence": "high | medium | low",
  "limitations": ["資料不足或不可判斷之處"]
}}

合成指標:
{_compact_text(json.dumps(synthesis_result, ensure_ascii=False), 2000)}

波形統計:
{_compact_text(json.dumps(waveform_stats, ensure_ascii=False), 2000)}"""

        try:
            return _normalize_ai_json(safe_parse_json(self._complete(prompt, max_tokens=512)))
        except Exception as e:
            return {
                "timing_risk": 0,
                "area_risk": 0,
                "function_risk": 0,
                "summary": f"分析失敗：{e}",
                "evidence": [],
                "next_actions": [],
                "confidence": "low",
                "limitations": ["AI 風險分析未成功完成。"],
            }

    # ─── Bottleneck Detector ───

    def bottleneck_detector(self, dag_result: dict) -> dict:
        """根據 dependency graph 識別瓶頸節點，提供優化建議。"""
        if self._mock:
            return _mock_bottleneck_analysis()
        self._ensure_ready()

        prompt = f"""{AI_AUDIENCE_POLICY}
{JSON_OUTPUT_POLICY}

請根據 module dependency graph 判斷結構性瓶頸。
注意：輸入是 dependency graph，不是 STA timing path。
除非資料明確提供 timing path，否則不要宣稱任何節點是 timing critical path。

請只分析：
- 哪些 module 可能是結構匯流點、依賴集中點或維護風險
- 這些結構對可讀性、重用性、測試或後續優化的影響
- 可以採取的架構整理建議

回傳 JSON schema:
{{
  "bottlenecks": ["module_name1"],
  "impact": "2 句內說明結構性影響",
  "suggestions": "2 句內提出具體建議",
  "confidence": "high | medium | low",
  "limitations": ["不能從 dependency graph 判斷的事項"]
}}

Dependency graph:
{_compact_text(json.dumps(dag_result, ensure_ascii=False), 2000)}"""

        try:
            return _normalize_ai_json(safe_parse_json(self._complete(prompt)))
        except Exception as e:
            return {
                "bottlenecks": [],
                "impact": f"分析失敗：{e}",
                "suggestions": "",
                "confidence": "low",
                "limitations": ["AI 瓶頸分析未成功完成。"],
            }

    # ─── Compare Tradeoff ───

    def compare_tradeoff(
        self,
        version_a: dict,
        version_b: dict,
        diff: dict,
        recommended: str | None,
    ) -> str:
        """生成兩個 run 的 tradeoff 分析文字。"""
        if self._mock:
            return _mock_compare_tradeoff()
        self._ensure_ready()

        payload = {
            "version_a": _compact_compare_version(version_a),
            "version_b": _compact_compare_version(version_b),
            "diff": diff,
            "recommended": recommended,
        }
        prompt = f"""{AI_AUDIENCE_POLICY}

請比較兩個 Verilog analysis run，根據提供的 metrics 產生取捨摘要。

規則：
- 只使用輸入資料，不要補 invent 缺失測量。
- 不要逐項重述表格中所有數字。
- 若推薦版本存在，第一句直接說推薦哪個版本與主要原因。
- 若無明確推薦，第一句說明兩者接近或資料不足。
- 第二句說明主要 tradeoff。
- 第三句說明需要人工確認的 caveat。
- 回覆 2-4 句繁體中文，不使用 markdown table。

Comparison JSON:
{_compact_text(json.dumps(payload, ensure_ascii=False), 3500)}"""

        try:
            text = self._complete(prompt, max_tokens=512).strip()
            if not text:
                raise ValueError("AI comparison 回傳空內容。")
            return _compact_text(text, 500)
        except Exception as e:
            raise RuntimeError(f"AI comparison failed: {e}") from e

    # ─── 內部工具方法 ───

    def _ensure_ready(self) -> None:
        if self._mock:
            return
        if self.client and self.model:
            return
        detail = self._init_error or "AI provider 尚未成功初始化。"
        raise AIProviderUnavailable(
            f"USE_MOCK_AI=false，但 {self.provider} 未就緒：{detail}"
        )

    def _stream(self, prompt: str) -> Generator[str, None, None]:
        if self.provider == "gemini":
            # Gemini 目前以單次 complete 模擬 streaming 介面，非逐 token 串流
            yield self._complete(prompt)
            return

        with self.client.messages.stream(
            model=self.model,
            max_tokens=config.MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    def _complete(self, prompt: str, max_tokens: int = config.MAX_TOKENS) -> str:
        if self.provider == "gemini":
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
            return response.text or ""

        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text


# ─── 模組層級工具函式 ───

def _mock_verilog_insight() -> str:
    return (
        "Mock: 結論\n"
        "這個設計像是一個小型同步控制模組，主要行為包含狀態更新與輸出訊號產生。\n\n"
        "關鍵依據\n"
        "- parser 顯示模組介面清楚，輸入輸出訊號數量適中，適合先完成模擬與合成確認。\n\n"
        "資料限制\n"
        "- 目前 mock 內容不代表實際 timing、slack 或 waveform 結果。"
    )


def _mock_workflow_plan() -> dict:
    return {
        "steps": ["lint", "simulate", "synthesize", "dependency"],
        "reason": "Mock: 使用完整檢查流程，先確認語法、功能、合成指標與模組依賴關係。",
    }


def _mock_log_insight() -> dict:
    return {
        "events": ["Mock: lint、simulate 與 synthesize stage 皆已完成並留下可檢視紀錄。"],
        "warnings": ["Mock: 目前未看到會阻斷流程的 warning 或 error。"],
        "limitations": ["Mock: 這是展示用資料，不能代表實際工具輸出。"],
        "summary": "Mock: EDA 流程看起來順利完成，沒有明顯阻斷問題。",
    }


def _mock_debug_advisor() -> str:
    return (
        "Mock: 可能原因\n"
        "工具訊息顯示語法解析失敗，常見原因是 always block 內缺少分號或 begin/end 沒有成對。\n\n"
        "證據\n"
        "stderr 通常會指出發生錯誤的行號或 token，建議先檢查該行與前後兩行。\n\n"
        "修正建議\n"
        "先確認每個 assignment 結尾都有分號，再檢查 if/else、case 與 always block 的結構是否完整。\n\n"
        "需要確認\n"
        "若修正後仍失敗，請以真實 AI 模式重新送出完整 stderr 與 Verilog 內容。"
    )


def _mock_risk_analysis() -> dict:
    return {
        "timing_risk": 2.5,
        "area_risk": 3.0,
        "function_risk": 2.0,
        "summary": "Mock: 目前設計整體風險偏低，模擬與合成摘要看起來一致，適合進入下一輪人工檢查。",
        "evidence": ["Mock: 模擬流程已完成且合成摘要沒有顯示阻斷性錯誤，主要風險集中在後續 timing 資料尚未補齊。"],
        "next_actions": ["Mock: 建議先檢查 waveform 是否符合預期，再用同一組測試比較下一版的 cell count、warning 數量與控制邏輯變化。"],
        "confidence": "medium",
        "limitations": ["Mock: 這是展示用分析，尚未包含真實 STA timing、完整功能覆蓋率或實際晶片製程約束。"],
    }


def _mock_bottleneck_analysis() -> dict:
    return {
        "bottlenecks": ["Mock: controller"],
        "impact": "Mock: controller 看起來是主要控制匯流點，後續若功能擴充，可能讓測試與維護成本提高。",
        "suggestions": "Mock: 建議將狀態轉移、輸出解碼與資料路徑保持清楚分層，避免所有邏輯集中在單一 always block。",
        "confidence": "medium",
        "limitations": ["Mock: dependency graph 無法直接判斷真實 critical path。"],
    }


def _mock_compare_tradeoff() -> str:
    return (
        "Mock: 建議暫時選擇版本 B，因為它在展示資料中保留功能正確性，同時資源使用略低。"
        "主要取捨是版本 B 的結構較精簡，但仍需要用真實 waveform 與 warning 紀錄確認行為一致。"
    )


def _compact_compare_version(version: dict) -> dict:
    keys = (
        "filename",
        "sim_passed",
        "warning_count",
        "cell_count",
        "wire_count",
        "flip_flop_count",
        "critical_path_ns",
        "slack_ns",
    )
    return {key: version.get(key) for key in keys}
