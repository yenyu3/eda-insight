import re
import json


# ─── 公開 API ───

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


# ─── 內部解析函式 ───

def _strip_comments(code: str) -> str:
    """移除單行（//）和多行（/* */）註解，保留行號對應。"""
    code = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group().count('\n'), code, flags=re.DOTALL)
    code = re.sub(r'//[^\n]*', '', code)
    return code


def _extract_modules(code: str) -> list[dict]:
    """找出所有 module...endmodule 區塊並解析其內容。"""
    modules = []
    # 支援 module foo; 和 module foo(...); 兩種宣告
    pattern = re.compile(
        r'\bmodule\s+(\w+)\s*(?:#\s*\(.*?\))?\s*(?:\((.*?)\))?\s*;(.*?)endmodule',
        re.DOTALL,
    )
    for m in pattern.finditer(code):
        name = m.group(1)
        has_port_list = m.group(2) is not None
        port_list_raw = m.group(2) or ""
        body = m.group(3)

        ports = _parse_ports(port_list_raw, body, has_port_list)
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


def _extract_signals(port_list_raw: str, body: str) -> list[str]:
    """
    萃取所有 wire/reg 訊號名稱，來源包含：
    1. port list 中的 output reg / input reg（ANSI style，每個 port 一個名稱）
    2. module body 中的 wire/reg 宣告（支援逗號分隔多變數：reg a, b, c;）
    """
    signals = []

    # Port list 每條宣告只有一個名稱
    port_pattern = re.compile(r'\b(?:wire|reg)\s+(?:\[[\d:]+\]\s*)?(\w+)', re.IGNORECASE)
    for m in port_pattern.finditer(port_list_raw):
        signals.append(m.group(1))

    # Body 支援純名稱與含 bit range 的宣告
    body_pattern = re.compile(
        r'\b(?:wire|reg)\s+(?:\[[\d:]+\]\s*)?((?:\w+\s*,\s*)*\w+)\s*;',
        re.IGNORECASE,
    )
    for m in body_pattern.finditer(body):
        for name in m.group(1).split(','):
            name = name.strip()
            if name:
                signals.append(name)

    return list(dict.fromkeys(signals))


def _detect_logic_type(body: str) -> str:
    """根據 always/assign 區塊判斷邏輯類型，支援 Verilog 與 SystemVerilog 語法。"""
    has_sequential = (
        bool(re.search(r'\balways_ff\b', body, re.IGNORECASE))
        or bool(re.search(r'\balways_latch\b', body, re.IGNORECASE))
        or bool(re.search(r'\balways\s*@\s*\(\s*(?:posedge|negedge)', body, re.IGNORECASE))
    )
    has_combinational = (
        bool(re.search(r'\balways_comb\b', body, re.IGNORECASE))
        or bool(re.search(r'\balways\s*@\s*\(\s*\*', body, re.IGNORECASE))
        or bool(re.search(r'\bassign\b', body, re.IGNORECASE))
    )
    if has_sequential and has_combinational:
        return "mixed"
    if has_sequential:
        return "sequential"
    return "combinational"


def _parse_ports(port_list_raw: str, body: str, has_port_list: bool = True) -> list[dict]:
    """Parse ANSI and non-ANSI module ports."""
    ports = []
    seen = set()

    for decl in _split_port_declarations(port_list_raw):
        parsed = _parse_port_declaration(decl)
        if not parsed:
            continue
        direction, width, names = parsed
        for pname in names:
            if pname not in seen:
                ports.append({"name": pname, "direction": direction, "width": width})
                seen.add(pname)

    if not ports and has_port_list and port_list_raw.strip():
        header_names = {
            p.strip()
            for p in port_list_raw.split(",")
            if re.match(r'^\s*\w+\s*$', p)
        }
        body_decl_pattern = re.compile(
            r'(?:^|(?<=;))\s*(input|output|inout)\s+(?:(?:reg|wire|logic)\s+)?(?:\[(\d+)\s*:\s*(\d+)\]\s*)?([^;]+);',
            re.IGNORECASE | re.MULTILINE,
        )
        for m in body_decl_pattern.finditer(body):
            direction = m.group(1).lower()
            high, low = m.group(2), m.group(3)
            width = (abs(int(high) - int(low)) + 1) if high is not None else 1
            for pname in _extract_decl_names(m.group(4)):
                if pname in header_names and pname not in seen:
                    ports.append({"name": pname, "direction": direction, "width": width})
                    seen.add(pname)

    return ports


def _split_port_declarations(port_list_raw: str) -> list[str]:
    declarations = []
    current = []
    depth = 0
    for ch in port_list_raw:
        if ch == "[":
            depth += 1
        elif ch == "]" and depth > 0:
            depth -= 1
        if ch == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                declarations.append(part)
            current = []
        else:
            current.append(ch)

    part = "".join(current).strip()
    if part:
        declarations.append(part)

    merged = []
    active = ""
    for part in declarations:
        if re.match(r'^(input|output|inout)\b', part, re.IGNORECASE):
            if active:
                merged.append(active)
            active = part
        elif active:
            active += ", " + part
        else:
            merged.append(part)
    if active:
        merged.append(active)
    return merged


def _parse_port_declaration(decl: str) -> tuple[str, int, list[str]] | None:
    m = re.match(
        r'^\s*(input|output|inout)\s+(?:(?:reg|wire|logic|signed|unsigned)\s+)*'
        r'(?:\[(\d+)\s*:\s*(\d+)\]\s*)?(.+)$',
        decl,
        re.IGNORECASE | re.DOTALL,
    )
    if not m:
        return None
    direction = m.group(1).lower()
    high, low = m.group(2), m.group(3)
    width = (abs(int(high) - int(low)) + 1) if high is not None else 1
    return direction, width, _extract_decl_names(m.group(4))


def _extract_decl_names(raw: str) -> list[str]:
    names = []
    for part in raw.split(","):
        part = re.sub(r'=.*$', '', part).strip()
        m = re.match(r'(\w+)', part)
        if m:
            names.append(m.group(1))
    return names


def _extract_instantiations(body: str, current_module: str) -> list[str]:
    keywords = {
        "module", "endmodule", "input", "output", "inout", "wire", "reg",
        "logic", "always", "always_ff", "always_comb", "always_latch",
        "assign", "initial", "begin", "end", "if", "else", "case",
        "endcase", "casez", "casex", "for", "while", "parameter", "localparam",
        "posedge", "negedge", "integer", "generate", "endgenerate",
        "task", "endtask", "function", "endfunction", "automatic",
        "fork", "join", "disable", "force", "release", "event",
        "time", "realtime", "defparam", "repeat", "forever",
        "supply0", "supply1", "tri", "signed", "unsigned",
    }
    insts = []
    patterns = [
        re.compile(r'(?:^|(?<=;))\s*(\w+)\s*#\s*\([\s\S]*?\)\s+(\w+)\s*\(', re.MULTILINE),
        re.compile(r'(?:^|(?<=;))\s*(\w+)\s+(\w+)\s*\(', re.MULTILINE),
    ]
    for pattern in patterns:
        for m in pattern.finditer(body):
            module_name = m.group(1)
            if module_name.lower() not in keywords and module_name != current_module:
                insts.append(module_name)
    return list(dict.fromkeys(insts))


def _check_lint(code: str, modules: list[dict]) -> list[dict]:
    """
    執行基本 Lint 檢查（heuristic，非嚴格分析，可能有誤報）。
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


# ─── 測試入口 ───

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "../sample_verilog/counter_4bit.v"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    result = parse_verilog(content)
    print(json.dumps(result, ensure_ascii=False, indent=2))
