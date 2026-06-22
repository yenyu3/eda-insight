import os
import json
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
        self._mock = True

        if config.USE_MOCK_AI:
            return

        if self.provider == "gemini":
            self._init_gemini()
        else:
            self.provider = "anthropic"
            self._init_anthropic()

    def _init_anthropic(self) -> None:
        """初始化 Anthropic client；失敗時維持 mock 模式。"""
        if anthropic is None:
            return

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key or api_key in {"your-key-here", "your-anthropic-key-here"}:
            return

        try:
            self.client = anthropic.Anthropic(api_key=api_key)
            self.model = config.ANTHROPIC_MODEL
            self._mock = False
        except Exception:
            self.client = None
            self._mock = True

    def _init_gemini(self) -> None:
        """初始化 Gemini client；失敗時維持 mock 模式。"""
        if genai is None:
            return

        api_key = os.environ.get("GEMINI_API_KEY", "")
        if not api_key or api_key == "your-gemini-key-here":
            return

        try:
            self.client = genai.Client(api_key=api_key)
            self.model = config.GEMINI_MODEL
            self._mock = False
        except Exception:
            self.client = None
            self._mock = True

    # ─── Verilog Insight ───

    def verilog_insight(self, parser_result: dict) -> Generator[str, None, None]:
        """根據 verilog_parser 輸出生成電路功能說明（串流版本）。"""
        if self._mock:
            yield from mock_stream(
                "這是一個 4 位元計數器電路，具有同步重置與使能控制。電路複雜度低，結構清晰。"
            )
            return

        prompt = f"""你是 EDA 領域的技術顧問。根據以下 Verilog 解析結果，用繁體中文說明：
1. 這個電路的功能是什麼
2. 電路複雜度評估（module 數量、port 數量）
3. 有哪些潛在問題需要注意
請用清楚易懂的語言，讓非電路工程師也能理解。

Verilog 解析結果：{json.dumps(parser_result, ensure_ascii=False)[:2000]}"""
        yield from self._stream(prompt)

    # ─── Workflow Planner ───

    def workflow_planner(self, verilog_insight: str, user_goals: str) -> dict:
        """根據電路資訊與使用者目標，決定本次 pipeline 要執行哪些步驟。"""
        fallback = {
            "steps": list(config.FIXED_PIPELINE),
            "reason": "fallback: AI 回傳格式有誤",
        }

        if self._mock:
            return {
                "steps": ["simulate", "synthesize", "dependency"],
                "reason": "mock: 預設流程",
            }

        prompt = f"""你是 EDA workflow 規劃專家。根據以下資訊，決定這次要執行哪些分析步驟。
steps 只能從 ["lint", "simulate", "synthesize", "dependency"] 中選擇，可以選一個或多個。
回傳純 JSON，不要任何 markdown backtick 或說明文字：
{{
  "steps": ["simulate", "synthesize"],
  "reason": "原因說明"
}}

電路資訊：{verilog_insight[:1000]}
使用者目標：{user_goals}"""

        try:
            raw = self._complete(prompt, max_tokens=256)
            data = safe_parse_json(raw)
            steps = data.get("steps", [])
            if not steps or not all(s in config.VALID_STEPS for s in steps):
                return fallback
            return {"steps": steps, "reason": data.get("reason", "")}
        except Exception:
            return fallback

    # ─── Log Insight ───

    def log_insight(self, log_text: str) -> dict:
        """分析 Icarus Verilog / Yosys 的 stdout log，回傳結構化摘要。"""
        if self._mock:
            return {
                "events": [],
                "warnings": [],
                "summary": "Mock: log 分析完成，無重大問題。",
            }

        prompt = f"""你是 EDA 工具 log 分析專家。分析以下 log，回傳純 JSON，不要 markdown backtick。
JSON 字串值內不要使用 Markdown、星號粗體、項目符號或標題語法：
{{
  "events": ["重要事件1", "重要事件2"],
  "warnings": ["warning 說明1"],
  "summary": "整體摘要（繁體中文，2-3 句話）"
}}

Log 內容（最多 2000 字元）：
{log_text[:2000]}"""

        try:
            return safe_parse_json(self._complete(prompt))
        except Exception as e:
            return {"events": [], "warnings": [], "summary": f"分析失敗：{e}"}

    # ─── Debug Advisor ───

    def debug_advisor(self, stderr_text: str, verilog_content: str) -> Generator[str, None, None]:
        """分析 EDA 工具的 stderr 錯誤訊息，串流回傳修正建議。"""
        if self._mock:
            yield from mock_stream(
                "偵測到語法錯誤：第 5 行缺少分號。建議在 count <= count + 1 後加上 ;。"
            )
            return

        prompt = f"""你是 Verilog 除錯專家。根據以下錯誤訊息與程式碼，用繁體中文說明：
1. 錯誤類型與發生原因
2. 問題所在行號
3. 具體修正方式（可附修正後的程式碼片段）

錯誤訊息：
{stderr_text[:1000]}

Verilog 程式碼：
{verilog_content[:1500]}"""
        yield from self._stream(prompt)

    # ─── Risk Analyzer ───

    def risk_analyzer(self, synthesis_result: dict, waveform_stats: dict) -> dict:
        """根據合成指標與波形統計，回傳風險評分（0-10）。"""
        if self._mock:
            return {
                "timing_risk": 2.5,
                "area_risk": 4.0,
                "function_risk": 1.0,
                "summary": "Mock: 電路整體風險偏低。",
            }

        prompt = f"""你是 EDA 設計風險分析師。根據以下合成與模擬資料，評估設計風險。
分數範圍 0-10（越高越危險）。回傳純 JSON，不要 markdown backtick。
JSON 字串值內不要使用 Markdown、星號粗體、項目符號或標題語法：
{{
  "timing_risk": 數字,
  "area_risk": 數字,
  "function_risk": 數字,
  "summary": "風險摘要（繁體中文，2-3 句話）"
}}

合成指標：{json.dumps(synthesis_result, ensure_ascii=False)}
波形統計：{json.dumps(waveform_stats, ensure_ascii=False)}"""

        try:
            return safe_parse_json(self._complete(prompt, max_tokens=512))
        except Exception as e:
            return {
                "timing_risk": 0,
                "area_risk": 0,
                "function_risk": 0,
                "summary": f"分析失敗：{e}",
            }

    # ─── Bottleneck Detector ───

    def bottleneck_detector(self, dag_result: dict) -> dict:
        """根據 dependency graph 識別瓶頸節點，提供優化建議。"""
        if self._mock:
            return {
                "bottlenecks": [],
                "impact": "Mock: 無明顯瓶頸。",
                "suggestions": "目前設計結構良好。",
            }

        prompt = f"""你是電路架構優化專家。根據以下 Module dependency graph，用繁體中文說明：
1. Critical path 上的瓶頸節點
2. 這些節點對整體設計的影響
3. 具體的優化建議

回傳純 JSON，不要 markdown backtick。
JSON 字串值內不要使用 Markdown、星號粗體、項目符號或標題語法：
{{
  "bottlenecks": ["module_name1"],
  "impact": "影響說明",
  "suggestions": "優化建議"
}}

DAG 資訊：{json.dumps(dag_result, ensure_ascii=False)[:1500]}"""

        try:
            return safe_parse_json(self._complete(prompt))
        except Exception as e:
            return {
                "bottlenecks": [],
                "impact": f"分析失敗：{e}",
                "suggestions": "",
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
        fallback = _fallback_compare_tradeoff(version_a, version_b, recommended)
        if self._mock:
            return fallback

        payload = {
            "version_a": _compact_compare_version(version_a),
            "version_b": _compact_compare_version(version_b),
            "diff": diff,
            "recommended": recommended,
        }
        prompt = f"""You are an EDA comparison assistant. Compare two Verilog analysis runs using only the provided metrics.

Write a concise tradeoff analysis in 2-4 sentences. Mention:
1. Which version is recommended, if any, and why.
2. Resource tradeoffs from cell count, wire count, flip-flops.
3. Timing tradeoffs from critical path and slack when available.
4. Correctness/simulation caveats when available.

Do not invent missing measurements. Avoid markdown tables.

Comparison JSON:
{json.dumps(payload, ensure_ascii=False)[:3500]}"""

        try:
            text = self._complete(prompt, max_tokens=512).strip()
            return text or fallback
        except Exception:
            return fallback

    # ─── 內部工具方法 ───

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


def _fallback_compare_tradeoff(a: dict, b: dict, recommended: str | None) -> str:
    picked = a if recommended == "a" else b if recommended == "b" else None
    if picked:
        reasons = []
        if a.get("sim_passed") is False or b.get("sim_passed") is False:
            reasons.append("simulation correctness")
        if a.get("cell_count") is not None and b.get("cell_count") is not None:
            reasons.append("cell-count efficiency")
        reason_text = " and ".join(reasons) if reasons else "available comparison metrics"
        return f"{picked['filename']} is the recommended choice based on {reason_text}."
    return (
        "The two runs are close on the available metrics. Review correctness, warnings, "
        "timing, slack, and waveform behavior before choosing one."
    )
