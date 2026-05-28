"""
verilog_parser.py — Verilog 靜態分析器

使用 Python re 模組解析 Verilog 原始碼，不呼叫任何外部工具。
萃取 module 結構、port 清單、訊號宣告、邏輯區塊、子模組例化，
以及基本 Lint 問題（如未使用訊號）。
"""

import re
import json


# ---------- 公開 API ----------

def parse_verilog(verilog_content: str) -> dict:
    """
    解析 Verilog 原始碼並回傳結構化 JSON-compatible dict。

    回傳格式：
    {
        "modules": [
            {
                "name": str,
                "ports": [{"name": str, "direction": str, "width": int}],
                "signals": [str],
                "logic_type": "sequential" | "combinational" | "mixed",
                "instantiations": [str]
            }
        ],
        "lint_issues": [{"type": str, "signal": str, "line": int}]
    }
    """
    verilog_content = _strip_comments(verilog_content)
    modules = _extract_modules(verilog_content)
    lint_issues = _check_lint(verilog_content, modules)
    return {"modules": modules, "lint_issues": lint_issues}


# ---------- 內部解析函式 ----------

def _strip_comments(code: str) -> str:
    """移除單行（//）和多行（/* */）註解，保留行號對應。"""
    code = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group().count('\n'), code, flags=re.DOTALL)
    code = re.sub(r'//[^\n]*', '', code)
    return code


def _extract_modules(code: str) -> list[dict]:
    """找出所有 module...endmodule 區塊並解析其內容。"""
    modules = []
    # port list 是 optional：module foo; 和 module foo(...); 兩種都支援
    pattern = re.compile(
        r'\bmodule\s+(\w+)\s*(?:#\s*\(.*?\))?\s*(?:\((.*?)\))?\s*;(.*?)endmodule',
        re.DOTALL,
    )
    for m in pattern.finditer(code):
        name = m.group(1)
        port_list_raw = m.group(2) or ""
        body = m.group(3)

        ports = _parse_ports(port_list_raw, body)
        signals = _extract_signals(port_list_raw, body)
        logic_type = _detect_logic_type(body)
        instantiations = _extract_instantiations(body, name)

        modules.append({
            "name": name,
            "ports": ports,
            "signals": signals,
            "logic_type": logic_type,
            "instantiations": instantiations,
        })
    return modules


def _parse_ports(port_list_raw: str, body: str) -> list[dict]:
    """
    解析 port 宣告，支援兩種風格：
    - ANSI style（port 方向直接寫在 module(...)）
    - Non-ANSI style（port 方向另外在 body 中宣告）
    """
    ports = []
    seen = set()

    # ANSI style：input/output/inout 直接在 port list 裡
    ansi_pattern = re.compile(
        r'\b(input|output|inout)\s+(?:reg\s+)?(?:\[(\d+):(\d+)\]\s*)?(\w+)', re.IGNORECASE
    )
    for m in ansi_pattern.finditer(port_list_raw):
        direction, high, low, pname = m.group(1), m.group(2), m.group(3), m.group(4)
        width = (int(high) - int(low) + 1) if high is not None else 1
        if pname not in seen:
            ports.append({"name": pname, "direction": direction.lower(), "width": width})
            seen.add(pname)

    # Non-ANSI style fallback：從 body 補充
    if not ports:
        for m in ansi_pattern.finditer(body):
            direction, high, low, pname = m.group(1), m.group(2), m.group(3), m.group(4)
            width = (int(high) - int(low) + 1) if high is not None else 1
            if pname not in seen:
                ports.append({"name": pname, "direction": direction.lower(), "width": width})
                seen.add(pname)

    return ports


def _extract_signals(port_list_raw: str, body: str) -> list[str]:
    """
    萃取所有 wire/reg 訊號名稱，來源包含：
    1. port list 中的 output reg / input reg（ANSI style，每個 port 一個名稱）
    2. module body 中的 wire/reg 宣告（支援逗號分隔多變數：reg a, b, c;）
    """
    signals = []

    # Port list：每條 port 宣告只有一個名稱，用簡單 pattern
    port_pattern = re.compile(r'\b(?:wire|reg)\s+(?:\[[\d:]+\]\s*)?(\w+)', re.IGNORECASE)
    for m in port_pattern.finditer(port_list_raw):
        signals.append(m.group(1))

    # Body：支援 `reg a, b, c;` 和 `wire [3:0] x;` 兩種格式
    body_pattern = re.compile(
        r'\b(?:wire|reg)\s+(?:\[[\d:]+\]\s*)?((?:\w+\s*,\s*)*\w+)\s*;',
        re.IGNORECASE,
    )
    for m in body_pattern.finditer(body):
        for name in m.group(1).split(','):
            name = name.strip()
            if name:
                signals.append(name)

    return list(dict.fromkeys(signals))  # 去重並保持順序


def _detect_logic_type(body: str) -> str:
    """根據 always/assign 區塊判斷邏輯類型。"""
    has_sequential = bool(re.search(r'\balways\s*@\s*\(\s*(?:posedge|negedge)', body, re.IGNORECASE))
    has_combinational = bool(re.search(r'\balways\s*@\s*\(\s*\*', body, re.IGNORECASE)) or \
                        bool(re.search(r'\bassign\b', body, re.IGNORECASE))
    if has_sequential and has_combinational:
        return "mixed"
    if has_sequential:
        return "sequential"
    return "combinational"


def _extract_instantiations(body: str, current_module: str) -> list[str]:
    """
    找出子模組例化（module instantiation）的模組名稱。
    排除關鍵字（always, assign, if, else, begin, end 等）以避免誤判。
    """
    keywords = {
        "module", "endmodule", "input", "output", "inout", "wire", "reg",
        "always", "assign", "initial", "begin", "end", "if", "else", "case",
        "endcase", "for", "while", "parameter", "localparam", "posedge",
        "negedge", "integer", "generate", "endgenerate",
    }
    insts = []
    # 格式：模組名 實例名 (...)
    pattern = re.compile(r'\b(\w+)\s+(\w+)\s*\(', re.MULTILINE)
    for m in pattern.finditer(body):
        module_name = m.group(1)
        if module_name.lower() not in keywords and module_name != current_module:
            insts.append(module_name)
    return list(dict.fromkeys(insts))


def _check_lint(code: str, modules: list[dict]) -> list[dict]:
    """
    執行基本 Lint 檢查，目前包含：
    - unused_wire：宣告但只出現一次（僅宣告，未在其他地方使用）的 wire/reg 訊號
    """
    issues = []
    for module in modules:
        for sig in module.get("signals", []):
            # 若訊號名稱在整個程式中出現次數 <= 1 視為未使用
            occurrences = len(re.findall(r'\b' + re.escape(sig) + r'\b', code))
            if occurrences <= 1:
                line = _find_signal_line(code, sig)
                issues.append({"type": "unused_wire", "signal": sig, "line": line})
    return issues


def _find_signal_line(code: str, signal: str) -> int:
    """找出訊號第一次出現的行號（1-based）。"""
    for i, line in enumerate(code.splitlines(), start=1):
        if re.search(r'\b' + re.escape(signal) + r'\b', line):
            return i
    return 0


# ---------- 測試入口 ----------

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "../sample_verilog/counter_4bit.v"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    result = parse_verilog(content)
    print(json.dumps(result, ensure_ascii=False, indent=2))
