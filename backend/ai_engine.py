"""
ai_engine.py — AI 分析引擎

封裝 Anthropic Claude API 的所有呼叫。
模型固定使用 claude-sonnet-4-20250514，max_tokens=1024。
提供六個功能模組：verilog_insight、workflow_planner、log_insight、
debug_advisor、risk_analyzer、bottleneck_detector。
"""

import os
import json
import re
from typing import Generator

try:
    import anthropic
except ImportError:
    anthropic = None

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1024
VALID_STEPS = {"lint", "simulate", "synthesize", "dependency"}


def _use_mock() -> bool:
    """每次呼叫時動態讀取，確保 dotenv 生效後的值能被正確取得。"""
    return os.environ.get("USE_MOCK_AI", "false").lower() == "true"


class AIEngine:
    """所有 AI 分析功能的統一入口。"""

    def __init__(self):
        self.client = None
        self._mock = True  # 預設 mock，成功建立 client 才設 False

        if _use_mock():
            return  # mock mode，直接結束

        if anthropic is None:
            return  # 套件未安裝，fallback mock

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key or api_key == "your-key-here":
            return  # key 未設定，fallback mock

        try:
            self.client = anthropic.Anthropic(api_key=api_key)
            self._mock = False
        except Exception:
            # 任何初始化錯誤（如 proxies 相容性問題）都 fallback mock
            self.client = None
            self._mock = True

    # ------------------------------------------------------------------
    # 1. verilog_insight — 電路功能說明（streaming，MVP 必做）
    # ------------------------------------------------------------------

    def verilog_insight(self, parser_result: dict) -> Generator[str, None, None]:
        """
        根據 verilog_parser 輸出生成電路功能說明（串流版本）。

        Args:
            parser_result: verilog_parser.parse_verilog() 的輸出 dict

        Yields:
            AI 回傳的文字片段（供 SSE 串流使用）
        """
        if self._mock:
            yield from _mock_stream("這是一個 4 位元計數器電路，具有同步重置與使能控制。電路複雜度低，結構清晰。")
            return

        prompt = f"""你是 EDA 領域的技術顧問。根據以下 Verilog 解析結果，用繁體中文說明：
1. 這個電路的功能是什麼
2. 電路複雜度評估（module 數量、port 數量）
3. 有哪些潛在問題需要注意
請用清楚易懂的語言，讓非電路工程師也能理解。

Verilog 解析結果：{json.dumps(parser_result, ensure_ascii=False)[:2000]}"""

        yield from self._stream(prompt)

    # ------------------------------------------------------------------
    # 2. workflow_planner — 動態 pipeline 規劃（進階功能，MVP 完成後實作）
    # ------------------------------------------------------------------

    def workflow_planner(self, verilog_insight: str, user_goals: str) -> dict:
        """
        根據電路資訊與使用者目標，決定本次 pipeline 要執行哪些步驟。
        回傳包含 steps 清單的 dict；若 AI 回傳格式有誤，自動 fallback 到預設流程。

        Args:
            verilog_insight: verilog_insight() 的輸出文字
            user_goals: 使用者選擇的分析目標描述

        Returns:
            {"steps": ["simulate", "synthesize"], "reason": str}
        """
        fallback = {"steps": ["lint", "simulate", "synthesize", "dependency"], "reason": "fallback: AI 回傳格式有誤"}

        if self._mock:
            return {"steps": ["simulate", "synthesize", "dependency"], "reason": "mock: 預設流程"}

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
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = response.content[0].text
            data = _safe_parse_json(raw)
            steps = data.get("steps", [])
            # 驗證：所有步驟必須在 VALID_STEPS 中
            if not steps or not all(s in VALID_STEPS for s in steps):
                return fallback
            return {"steps": steps, "reason": data.get("reason", "")}
        except Exception:
            return fallback

    # ------------------------------------------------------------------
    # 3. log_insight — EDA log 分析（MVP 必做）
    # ------------------------------------------------------------------

    def log_insight(self, log_text: str) -> dict:
        """
        分析 Icarus Verilog / Yosys 的 stdout log，回傳結構化摘要。

        Args:
            log_text: EDA 工具輸出的完整 log 文字

        Returns:
            {"events": [...], "warnings": [...], "summary": str}
        """
        if self._mock:
            return {"events": [], "warnings": [], "summary": "Mock: log 分析完成，無重大問題。"}

        prompt = f"""你是 EDA 工具 log 分析專家。分析以下 log，回傳純 JSON，不要 markdown backtick：
{{
  "events": ["重要事件1", "重要事件2"],
  "warnings": ["warning 說明1"],
  "summary": "整體摘要（繁體中文，2-3 句話）"
}}

Log 內容（最多 2000 字元）：
{log_text[:2000]}"""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            return _safe_parse_json(response.content[0].text)
        except Exception as e:
            return {"events": [], "warnings": [], "summary": f"分析失敗：{e}"}

    # ------------------------------------------------------------------
    # 4. debug_advisor — 錯誤診斷（streaming，MVP 必做）
    # ------------------------------------------------------------------

    def debug_advisor(self, stderr_text: str, verilog_content: str) -> Generator[str, None, None]:
        """
        分析 EDA 工具的 stderr 錯誤訊息，串流回傳修正建議。

        Args:
            stderr_text: 錯誤訊息（iverilog / yosys stderr）
            verilog_content: 原始 Verilog 程式碼

        Yields:
            診斷文字片段
        """
        if self._mock:
            yield from _mock_stream("偵測到語法錯誤：第 5 行缺少分號。建議在 `count <= count + 1` 後加上 `;`。")
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

    # ------------------------------------------------------------------
    # 5. risk_analyzer — 設計風險評估（MVP 必做）
    # ------------------------------------------------------------------

    def risk_analyzer(self, synthesis_result: dict, waveform_stats: dict) -> dict:
        """
        根據合成指標與波形統計，回傳風險評分（0-10）。

        Args:
            synthesis_result: report_parser.parse_synthesis_report() 輸出
            waveform_stats: vcd_parser 的 stats 欄位

        Returns:
            {"timing_risk": float, "area_risk": float, "function_risk": float, "summary": str}
        """
        if self._mock:
            return {"timing_risk": 2.5, "area_risk": 4.0, "function_risk": 1.0, "summary": "Mock: 電路整體風險偏低。"}

        prompt = f"""你是 EDA 設計風險分析師。根據以下合成與模擬資料，評估設計風險。
分數範圍 0-10（越高越危險）。回傳純 JSON，不要 markdown backtick：
{{
  "timing_risk": 數字,
  "area_risk": 數字,
  "function_risk": 數字,
  "summary": "風險摘要（繁體中文，2-3 句話）"
}}

合成指標：{json.dumps(synthesis_result, ensure_ascii=False)}
波形統計：{json.dumps(waveform_stats, ensure_ascii=False)}"""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=512,
                messages=[{"role": "user", "content": prompt}],
            )
            return _safe_parse_json(response.content[0].text)
        except Exception as e:
            return {"timing_risk": 0, "area_risk": 0, "function_risk": 0, "summary": f"分析失敗：{e}"}

    # ------------------------------------------------------------------
    # 6. bottleneck_detector — 瓶頸節點識別（MVP 必做）
    # ------------------------------------------------------------------

    def bottleneck_detector(self, dag_result: dict) -> dict:
        """
        根據 dependency graph 識別瓶頸節點，提供優化建議。

        Args:
            dag_result: dependency_analyzer.build_dag() 輸出

        Returns:
            {"bottlenecks": [str], "impact": str, "suggestions": str}
        """
        if self._mock:
            return {"bottlenecks": [], "impact": "Mock: 無明顯瓶頸。", "suggestions": "目前設計結構良好。"}

        prompt = f"""你是電路架構優化專家。根據以下 Module dependency graph，用繁體中文說明：
1. Critical path 上的瓶頸節點
2. 這些節點對整體設計的影響
3. 具體的優化建議

回傳純 JSON，不要 markdown backtick：
{{
  "bottlenecks": ["module_name1"],
  "impact": "影響說明",
  "suggestions": "優化建議"
}}

DAG 資訊：{json.dumps(dag_result, ensure_ascii=False)[:1500]}"""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                messages=[{"role": "user", "content": prompt}],
            )
            return _safe_parse_json(response.content[0].text)
        except Exception as e:
            return {"bottlenecks": [], "impact": f"分析失敗：{e}", "suggestions": ""}

    # ------------------------------------------------------------------
    # 內部工具方法
    # ------------------------------------------------------------------

    def _stream(self, prompt: str) -> Generator[str, None, None]:
        """執行 streaming 呼叫，yield 每個文字片段。"""
        with self.client.messages.stream(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text


# ------------------------------------------------------------------
# 模組層級工具函式
# ------------------------------------------------------------------

def _safe_parse_json(text: str) -> dict:
    """清除 AI 可能附加的 markdown fence 後解析 JSON；解析失敗回傳空 dict。"""
    cleaned = text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return {}


def _mock_stream(text: str) -> Generator[str, None, None]:
    """回傳假串流資料，每次 yield 一個詞（以空格分割）。"""
    for word in text.split():
        yield word + " "


# ---------- 測試入口 ----------

if __name__ == "__main__":
    engine = AIEngine()
    mock_parser = {
        "modules": [{"name": "counter_4bit", "ports": [], "signals": [], "logic_type": "sequential", "instantiations": []}],
        "lint_issues": [],
    }
    print("=== verilog_insight (mock) ===")
    for chunk in engine.verilog_insight(mock_parser):
        print(chunk, end="", flush=True)
    print()
