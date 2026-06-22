import re
import json


# ─── 公開 API ────────────────────────────────────────────────────────────────

def extract_flowchart(verilog_content: str) -> dict:
    """
    從 Verilog 原始碼抽取流程圖資訊。

    回傳結構：
    {
        "always_blocks": [...],
        "assign_blocks": [...],
        "state_diagram": {...} | None,
        "signal_dependency_map": {...},
        "summary": str,
        "detail_level": "complete" | "summarized",
        "truncated": bool,
        "truncation_reasons": [...],
        "hidden_count": int
    }
    """
    ctx = _new_context()
    code = _strip_comments(verilog_content)
    always_blocks = _find_always_blocks(code, ctx)
    assign_blocks = _find_assign_stmts(code)
    state_diagram = _build_state_diagram(always_blocks)
    return {
        "always_blocks": always_blocks,
        "assign_blocks": assign_blocks,
        "state_diagram": state_diagram,
        "signal_dependency_map": _build_signal_dependency_map(always_blocks, assign_blocks),
        "summary": _summarize_flowchart(always_blocks, assign_blocks),
        "detail_level": "summarized" if ctx["truncated"] else "complete",
        "truncated": ctx["truncated"],
        "truncation_reasons": sorted(ctx["truncation_reasons"]),
        "hidden_count": ctx["hidden_count"],
    }


def _new_context() -> dict:
    return {
        "truncated": False,
        "truncation_reasons": set(),
        "hidden_count": 0,
    }


def _mark_truncated(ctx: dict, reason: str, hidden_count: int = 0) -> None:
    ctx["truncated"] = True
    ctx["truncation_reasons"].add(reason)
    ctx["hidden_count"] += max(0, hidden_count)


# ─── 前置處理 ─────────────────────────────────────────────────────────────────

def _strip_comments(code: str) -> str:
    """移除 /* ... */ 與 // 註解。"""
    code = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group().count('\n'), code, flags=re.DOTALL)
    code = re.sub(r'//[^\n]*', '', code)
    return code


# ─── begin/end 平衡掃描（所有巢狀解析共用） ──────────────────────────────────

def _scan_begin_end(s: str) -> tuple[str, str]:
    """
    從字串開頭掃描一個平衡 begin...end block。
    回傳 (完整 block 含 begin/end, 剩餘字串)。
    假設 s 以 'begin' 開頭。
    """
    depth = 0
    i = 0
    while i < len(s):
        if s[i] in 'bBeE':
            kw = re.match(r'\b(begin|end)\b', s[i:], re.IGNORECASE)
            if kw:
                depth += 1 if kw.group(1).lower() == 'begin' else -1
                if depth == 0:
                    end_pos = i + len(kw.group(0))
                    return s[:end_pos], s[end_pos:]
                i += len(kw.group(0))
                continue
        i += 1
    return s, ''


def _extract_block(code: str) -> tuple[str, str]:
    """
    從 code 開頭取出一個 logical block：
    - 若以 begin 開頭：取 balanced begin...end
    - 否則：取到第一個 ;
    回傳 (block, 剩餘)。
    """
    s = code.strip()
    if re.match(r'^begin\b', s, re.IGNORECASE):
        return _scan_begin_end(s)
    sem = s.find(';')
    if sem == -1:
        return s, ''
    return s[:sem + 1], s[sem + 1:]


def _unwrap_begin_end(body: str) -> str:
    """移除最外層 begin...end wrapper，回傳內層字串。"""
    s = body.strip()
    if not re.match(r'^begin\b', s, re.IGNORECASE):
        return s
    block, _ = _scan_begin_end(s)
    return block[5:-3].strip()


# ─── 語意轉譯層 ───────────────────────────────────────────────────────────────

_FSM_STATE_NAMES = {"state", "cur_state", "current_state", "next_state", "ns", "ps", "fsm_state", "state_reg"}
_FSM_CASE_PREFIXES = tuple(f"case({s}" for s in _FSM_STATE_NAMES)

SEMANTIC_TO_BUSINESS: dict[str, str] = {
    "每次時鐘更新時觸發": "定時運作",
    "時序邏輯更新":       "定時更新狀態",
    "輸入一有變動立即執行": "即時反應",
    "收到重置信號":       "系統重新開始",
    "資料就緒且可以接收": "可以開始處理",
    "有新資料進來":       "有新資料可處理",
    "系統準備好了":       "可以接收資料",
    "功能開關打開":       "功能已啟用",
    "這輪已完成":         "任務結束了",
    "依目前流程階段":     "走到哪個步驟了",
    "計時信號到":         "計時器觸發",
    "計數達到預設值":     "已達目標數量",
    "條件判斷":           "是否符合條件",
    "退回待機":           "等待下一個工作",
    "標記任務完成":       "任務執行完畢",
    "不做更動":           "繼續等待",
    "計數 +1":            "記錄進度加一",
    "計數歸零":           "重新開始計數",
    "輸出新結果":         "結果已更新",
    "準備傳送資料":       "資料準備送出",
    "更新狀態":           "更新內部資料",
    "省略細節":           "（簡化顯示）",
}

SIGNAL_HUMANIZE: dict[str, str] = {
    "rst_n":    "重置訊號",
    "rst":      "重置訊號",
    "reset":    "重置訊號",
    "clk":      "時鐘",
    "valid":    "有效輸入",
    "ready":    "就緒訊號",
    "done":     "完成訊號",
    "enable":   "啟用訊號",
    "en":       "啟用訊號",
    "state":    "目前狀態",
    "next_state": "下一狀態",
    "count":    "計數值",
    "baud_tick": "計時器",
    "baud_cnt": "波特率計數",
    "bit_cnt":  "位元計數",
    "tx_valid": "傳送有效訊號",
    "tx":       "傳送資料",
    "rx":       "接收資料",
    "out":      "輸出",
    "output":   "輸出",
}


def _humanize_signals(signals: list[str]) -> str:
    humanized = [SIGNAL_HUMANIZE.get(sig, sig) for sig in signals]
    if len(humanized) == 1:
        return humanized[0]
    return " 和 ".join(humanized)


def _translate_condition(expr: str) -> str:
    """把條件式轉成語意標籤（Semantic Layer）。"""
    raw = expr.strip()
    lower = raw.lower()

    if raw.startswith("case("):
        inner = raw[5:-1] if raw.endswith(")") else raw[5:]
        inner = inner.strip()
        if inner in _FSM_STATE_NAMES:
            return "依目前流程階段"
        return f"依 {inner} 的值分流"

    if re.search(r'\brst_n\b|\brst\b|\breset\b', lower):
        return "收到重置信號"

    if re.search(r'\bvalid\b', lower) and re.search(r'\bready\b', lower):
        return "資料就緒且可以接收"

    if re.search(r'\bdone\b|\bfinish\b|\bcomplete\b', lower):
        return "這輪已完成"

    if re.search(r'^enable$|^en$', lower):
        return "功能開關打開"
    if re.search(r'\benable\b', lower) and len(lower) < 20:
        return "功能開關打開"

    if re.search(r'\bvalid\b', lower):
        return "有新資料進來"

    if re.search(r'\bready\b', lower):
        return "系統準備好了"

    if re.search(r'\b(?:state|ns|ps|cur_state|current_state|next_state|fsm_state)\b', lower):
        return "依目前流程階段"

    if re.search(r'\bbaud_tick\b|\bclk_tick\b|\btick\b', lower):
        return "計時信號到"

    if re.search(r'\b(?:bit_cnt|baud_cnt|count|cnt)\b.*==', lower):
        return "計數達到預設值"

    return "條件判斷"


def _translate_process(label: str) -> str:
    """把 assignment 標籤轉成語意描述（Semantic Layer）。"""
    if label == "(no change)":
        return "不做更動"
    if label.startswith("[...]") or label.startswith("[loop:"):
        return "省略細節"

    lower = label.lower().strip()

    if re.search(r'\b(?:state|next_state)\s*(?:<=|=)\s*\w*idle\b', lower):
        return "退回待機"
    if re.search(r'\b(?:state|next_state)\s*(?:<=|=)\s*\w*(?:done|finish|complete)\b', lower):
        return "標記任務完成"
    m = re.match(r'(?:state|next_state|cur_state)\s*(?:<=|=)\s*([A-Za-z_]\w*)', lower)
    if m:
        state_name = m.group(1).upper()
        return f"切換到 {state_name}"

    if re.search(r'\b\w*count\w*\s*(?:<=|=)\s*(?:0|\'b0|\'d0|[0-9]+\'[bBdDhH][0]+)\b', lower):
        return "計數歸零"
    if re.search(r'\b(?:baud_cnt|bit_cnt|cnt)\s*(?:<=|=)\s*0\b', lower):
        return "計數歸零"

    if re.search(r'\b\w*count\w*\s*(?:<=|=)\s*\w+\s*\+\s*1', lower):
        return "計數 +1"
    if re.search(r'\b(?:baud_cnt|bit_cnt|cnt)\s*(?:<=|=)\s*\w+\s*\+\s*1', lower):
        return "計數 +1"

    lhs_m = re.match(r'([A-Za-z_]\w*)\s*(?:<=|=)', lower)
    if lhs_m:
        lhs = lhs_m.group(1)
        if re.search(r'^(?:out|output|y|result)$', lhs):
            return "輸出新結果"
        if re.search(r'^tx', lhs):
            return "準備傳送資料"
        if lhs in {"baud_cnt", "bit_cnt", "cnt"}:
            return "計數 +1" if '+' in label else "更新計數器"

    lines = [ln.strip() for ln in label.split('\n') if ln.strip() and '(+' not in ln]
    if len(lines) > 1:
        return f"同時更新 {len(lines)} 項資料"

    return "更新狀態"


def _to_business_label(semantic: str) -> str:
    """把語意標籤轉成產品人話（Business Layer）。"""
    result = SEMANTIC_TO_BUSINESS.get(semantic)
    if result:
        return result
    if semantic.startswith("切換到 "):
        return "進入下一個步驟"
    if semantic.startswith("依 ") and semantic.endswith(" 分流"):
        return "依條件選擇下一步"
    if semantic.startswith("依 ") and semantic.endswith(" 的值分流"):
        return "依條件選擇下一步"
    if semantic.startswith("同時更新 "):
        return "一次更新多筆資料"
    return semantic


def _translate_assign_intent(output: str, expression: str) -> str:
    """給 assign 陳述句產生語意摘要。"""
    expr = expression.strip()
    if re.search(r'(?<![&|])[&](?![&|])', expr):
        return "兩個條件都成立才輸出"
    if '&&' in expr:
        return "多個條件全部成立才輸出"
    if re.search(r'(?<![&|])[|](?![&|])', expr) or '||' in expr:
        return "任一條件成立就輸出"
    if expr.startswith('~') or expr.startswith('!'):
        return "輸出與輸入相反"
    if '?' in expr and ':' in expr:
        return "依條件在兩個值中選一個輸出"
    if expr.startswith('{') or output.startswith('{'):
        return "將多個訊號合併成一個輸出"
    return "直接把輸入傳到輸出"


def _semantic_trigger(trigger: str, trigger_type: str) -> str:
    if trigger == "always_ff":
        return "時序邏輯更新"
    if trigger_type == "sequential":
        return "每次時鐘更新時觸發"
    if trigger in {"always_comb", "always_latch"}:
        return "輸入一有變動立即執行"
    return "輸入一有變動立即執行"


def _business_trigger(trigger: str, trigger_type: str) -> str:
    sem = _semantic_trigger(trigger, trigger_type)
    return SEMANTIC_TO_BUSINESS.get(sem, sem)


# ─── always block 尋找 ────────────────────────────────────────────────────────

def _find_always_blocks(code: str, ctx: dict) -> list[dict]:
    results = []
    trigger_pattern = re.compile(
        r'\balways(?:_(ff|comb|latch))?\s*(?:@\s*\(([^)]*)\))?\s*',
        re.IGNORECASE | re.DOTALL,
    )
    matches = list(trigger_pattern.finditer(code))
    if len(matches) > 5:
        _mark_truncated(ctx, "always_block_limit", len(matches) - 5)

    for block_idx, m in enumerate(matches):
        if block_idx >= 5:
            break
        always_kind = (m.group(1) or "").lower()
        trigger_raw = (m.group(2) or "").strip()
        rest = code[m.end():].lstrip()

        if re.match(r'^begin\b', rest, re.IGNORECASE):
            body, _ = _scan_begin_end(rest)
        else:
            sem = rest.find(';')
            if sem == -1:
                continue
            body = rest[:sem + 1]

        trigger, trigger_type = _parse_trigger(trigger_raw, always_kind)
        start_id = f"ab_{block_idx}_start"
        counter = [0]
        block_start = _line_number_at(code, m.start())
        block_end = block_start + body.count("\n")
        nodes, edges, entry_id = _parse_body(body, block_idx, counter, ctx=ctx)

        sem_trigger = _semantic_trigger(trigger, trigger_type)
        biz_trigger = _business_trigger(trigger, trigger_type)
        trigger_node = {
            "id": start_id,
            "type": "trigger",
            "label": trigger,
            "display_label": _friendly_trigger(trigger, trigger_type),
            "semantic_label": sem_trigger,
            "business_label": biz_trigger,
            "detail": trigger,
            "source_line_start": block_start,
            "source_line_end": block_start,
        }
        nodes = [trigger_node] + nodes
        if entry_id:
            edges = [{"id": f"ab_{block_idx}_e_start", "source": start_id, "target": entry_id, "kind": "sequence"}] + edges

        assigned_signals = _collect_node_values(nodes, "assigned_signals")
        condition_signals = _collect_node_values(nodes, "condition_signals")
        block_role = _infer_block_role(nodes, assigned_signals, trigger_type)
        title = _block_title(block_idx, trigger, block_role)

        results.append({
            "id": f"ab_{block_idx}",
            "title": title,
            "trigger": trigger,
            "trigger_type": trigger_type,
            "block_role": block_role,
            "summary": _summarize_block(trigger, trigger_type, block_role, assigned_signals, condition_signals, nodes),
            "assigned_signals": assigned_signals,
            "condition_signals": condition_signals,
            "source_line_start": block_start,
            "source_line_end": block_end,
            "nodes": nodes,
            "edges": edges,
        })
    return results


def _parse_trigger(trigger_raw: str, always_kind: str = "") -> tuple[str, str]:
    """將 always 的觸發條件標準化，並回傳 (trigger, trigger_type)。"""
    if always_kind == "comb":
        return "always_comb", "combinational"
    if always_kind == "latch":
        return "always_latch", "combinational"
    if always_kind == "ff":
        return trigger_raw or "always_ff", "sequential"
    t = trigger_raw.strip()
    if re.search(r'\b(posedge|negedge)\b', t, re.IGNORECASE):
        return t, "sequential"
    return t if t else "*", "combinational"


# ─── body 解析（遞迴） ────────────────────────────────────────────────────────

def _parse_body(body: str, block_idx: int, counter: list, depth: int = 0, ctx: dict | None = None) -> tuple[list, list, str]:
    ctx = ctx or _new_context()
    body = _unwrap_begin_end(body)
    stripped = body.strip()

    if depth > 4:
        _mark_truncated(ctx, "nesting_depth_limit", 1)
        nid = _next_id(block_idx, counter, "p")
        return [_process_node(nid, f"[...] {_truncate(stripped, 48)}", kind="summary")], [], nid

    if_result = _try_parse_if(stripped, block_idx, counter, depth, ctx)
    if if_result is not None:
        return if_result

    case_result = _try_parse_case(stripped, block_idx, counter, depth, ctx)
    if case_result is not None:
        return case_result

    if re.match(r'\b(for|while|repeat|forever)\b', stripped, re.IGNORECASE):
        _mark_truncated(ctx, "loop_summary", 1)
        nid = _next_id(block_idx, counter, "p")
        return [_process_node(nid, f"[loop: {_truncate(stripped, 46)}]", kind="summary")], [], nid

    stmts = _split_top_level_stmts(stripped)
    if len(stmts) > 1:
        if any(_is_structural_stmt(stmt) for stmt in stmts):
            return _parse_stmt_sequence(stmts, block_idx, counter, depth, ctx)
        nid = _next_id(block_idx, counter, "p")
        return [_process_node(nid, _format_multi_stmt(stmts), assigned_signals=_assigned_from_stmts(stmts))], [], nid

    assign_match = re.match(r'([A-Za-z_][\w$]*(?:\s*\[[^\]]+\])?)\s*(<=|=)\s*(.+?);', stripped, re.DOTALL)
    if assign_match:
        nid = _next_id(block_idx, counter, "p")
        lhs = assign_match.group(1).strip()
        op = assign_match.group(2)
        rhs = _truncate(assign_match.group(3).strip(), 32)
        return [_process_node(nid, f"{lhs} {op} {rhs}", assigned_signals=[_base_signal(lhs)])], [], nid

    nid = _next_id(block_idx, counter, "p")
    return [_process_node(nid, _truncate(stripped, 48))], [], nid


def _decision_node(nid: str, label: str) -> dict:
    sem = _translate_condition(label)
    biz = _to_business_label(sem)
    return {
        "id": nid,
        "type": "decision",
        "label": label,
        "display_label": _friendly_condition(label),
        "semantic_label": sem,
        "business_label": biz,
        "detail": label,
        "condition_signals": _signals_from_expr(label),
    }


def _process_node(nid: str, label: str, assigned_signals: list[str] | None = None, kind: str = "process") -> dict:
    sem = _translate_process(label)
    biz = _to_business_label(sem)
    return {
        "id": nid,
        "type": "process",
        "label": label,
        "display_label": _friendly_process(label),
        "semantic_label": sem,
        "business_label": biz,
        "detail": label,
        "kind": kind,
        "assigned_signals": sorted(set(assigned_signals or [])),
    }


def _split_top_level_stmts(body: str) -> list[str]:
    """將 body 按頂層 ';' 分割，不進入 begin/end 或括號內。"""
    stmts = []
    depth_b = depth_p = depth_case = 0
    i = start = 0
    while i < len(body):
        ch = body[i]
        if ch in 'bBcCeE':
            kw = re.match(r'\b(begin|end|casez|casex|case|endcase)\b', body[i:], re.IGNORECASE)
            if kw:
                word = kw.group(1).lower()
                if word == 'begin':
                    depth_b += 1
                elif word == 'end':
                    depth_b -= 1
                elif word in {'case', 'casez', 'casex'}:
                    depth_case += 1
                elif word == 'endcase':
                    depth_case -= 1
                    if depth_b == 0 and depth_case == 0:
                        end_pos = i + len(kw.group(0))
                        stmt = body[start:end_pos].strip()
                        if stmt:
                            stmts.append(stmt)
                        start = end_pos
                        i = end_pos
                        continue
                i += len(kw.group(0))
                continue
        if ch == '(':
            depth_p += 1
        elif ch == ')':
            depth_p -= 1
        elif ch == ';' and depth_b == 0 and depth_p == 0 and depth_case == 0:
            stmt = body[start:i + 1].strip()
            if stmt:
                stmts.append(stmt)
            start = i + 1
        i += 1
    remaining = body[start:].strip()
    if remaining:
        stmts.append(remaining)
    return _merge_else_stmts(stmts)


def _merge_else_stmts(stmts: list[str]) -> list[str]:
    merged: list[str] = []
    for stmt in stmts:
        if re.match(r'\s*else\b', stmt, re.IGNORECASE) and merged:
            merged[-1] = f"{merged[-1]}\n{stmt}"
        else:
            merged.append(stmt)
    return merged


def _is_structural_stmt(stmt: str) -> bool:
    return re.match(r'\s*(if|casez|casex|case|for|while|repeat|forever)\b', stmt, re.IGNORECASE) is not None


def _parse_stmt_sequence(stmts: list[str], block_idx: int, counter: list, depth: int, ctx: dict):
    chunks = _group_sequence_chunks(stmts)
    nodes = []
    edges = []
    entry_id = ""
    previous_exits: list[str] = []

    for idx, chunk in enumerate(chunks):
        chunk_body = '\n'.join(chunk)
        chunk_nodes, chunk_edges, chunk_entry = _parse_body(chunk_body, block_idx, counter, depth, ctx)
        if not chunk_entry:
            continue

        nodes += chunk_nodes
        edges += chunk_edges
        if not entry_id:
            entry_id = chunk_entry

        for source in previous_exits:
            edges.append({
                "id": f"e_seq_{block_idx}_{idx}_{source}_{chunk_entry}",
                "source": source,
                "target": chunk_entry,
                "kind": "sequence",
            })

        previous_exits = _terminal_node_ids(chunk_nodes, chunk_edges)

    return nodes, edges, entry_id


def _group_sequence_chunks(stmts: list[str]) -> list[list[str]]:
    chunks: list[list[str]] = []
    pending_simple: list[str] = []

    for stmt in stmts:
        if _is_structural_stmt(stmt):
            if pending_simple:
                chunks.append(pending_simple)
                pending_simple = []
            chunks.append([stmt])
        else:
            pending_simple.append(stmt)

    if pending_simple:
        chunks.append(pending_simple)
    return chunks


def _terminal_node_ids(nodes: list[dict], edges: list[dict]) -> list[str]:
    node_ids = {node["id"] for node in nodes}
    sources = {edge["source"] for edge in edges}
    terminals = [node_id for node_id in node_ids if node_id not in sources]
    return terminals or list(node_ids)


def _format_multi_stmt(stmts: list[str]) -> str:
    """將多個 statement 格式化為緊湊多行 label（最多顯示 4 行）。"""
    lines = []
    for stmt in stmts:
        m = re.match(r'([A-Za-z_][\w$]*(?:\s*\[[^\]]+\])?)\s*(<=|=)\s*(.+?);', stmt.strip(), re.DOTALL)
        if m:
            lines.append(f"{m.group(1).strip()} {m.group(2)} {_truncate(m.group(3).strip(), 20)}")
        elif stmt.strip():
            lines.append(_truncate(stmt.strip(), 24))
    display = lines[:4]
    if len(lines) > 4:
        display.append(f"(+{len(lines) - 4} more)")
    return '\n'.join(display)


def _assigned_from_stmts(stmts: list[str]) -> list[str]:
    signals = []
    for stmt in stmts:
        m = re.match(r'\s*([A-Za-z_][\w$]*(?:\s*\[[^\]]+\])?)\s*(?:<=|=)\s*', stmt, re.DOTALL)
        if m:
            signals.append(_base_signal(m.group(1)))
    return sorted(set(signals))


# ─── if 解析 ─────────────────────────────────────────────────────────────────

def _try_parse_if(body: str, block_idx: int, counter: list, depth: int, ctx: dict):
    stripped = body.strip()
    m = re.match(r'if\s*\(', stripped, re.IGNORECASE)
    if not m:
        return None

    cond, after_pos = _extract_paren_cond(stripped, m.end() - 1)
    rest_after_cond = stripped[after_pos:].lstrip()

    then_body, after_then = _extract_block(rest_after_cond)

    else_body = None
    after_then_stripped = after_then.strip()
    if after_then_stripped.lower().startswith('else'):
        else_body = after_then_stripped[4:].strip()

    cond_id = _next_id(block_idx, counter, "c")
    nodes = [_decision_node(cond_id, cond.strip())]
    edges = []

    yes_nodes, yes_edges, yes_entry = _parse_body(then_body, block_idx, counter, depth + 1, ctx)
    nodes += yes_nodes
    edges += yes_edges
    if yes_entry:
        edges.append({"id": f"e_{cond_id}_yes", "source": cond_id, "target": yes_entry, "label": "YES", "kind": "branch"})

    if else_body:
        no_nodes, no_edges, no_entry = _parse_body(else_body, block_idx, counter, depth + 1, ctx)
        nodes += no_nodes
        edges += no_edges
        if no_entry:
            edges.append({"id": f"e_{cond_id}_no", "source": cond_id, "target": no_entry, "label": "NO", "kind": "branch"})
    else:
        hold_id = _next_id(block_idx, counter, "p")
        nodes.append(_process_node(hold_id, "(no change)"))
        edges.append({"id": f"e_{cond_id}_no", "source": cond_id, "target": hold_id, "label": "NO", "kind": "branch"})

    return nodes, edges, cond_id


def _extract_paren_cond(s: str, open_pos: int) -> tuple[str, int]:
    """
    從 open_pos 的 '(' 開始，用平衡括號追蹤，
    回傳 (括號內容, 閉括號後位置)。
    """
    depth = 0
    i = open_pos
    while i < len(s):
        if s[i] == '(':
            depth += 1
        elif s[i] == ')':
            depth -= 1
            if depth == 0:
                return s[open_pos + 1:i], i + 1
        i += 1
    return s[open_pos + 1:], len(s)


# ─── case 解析 ────────────────────────────────────────────────────────────────

def _try_parse_case(body: str, block_idx: int, counter: list, depth: int, ctx: dict):
    stripped = body.strip()
    m = re.match(r'case[zx]?\s*\((.+?)\)\s*', stripped, re.IGNORECASE | re.DOTALL)
    if not m:
        return None

    expr = m.group(1).strip()
    rest = stripped[m.end():]
    endcase_m = re.search(r'\bendcase\b', rest, re.IGNORECASE)
    if not endcase_m:
        return None
    case_body = rest[:endcase_m.start()]

    arms = _parse_case_arms_robust(case_body)

    case_id = _next_id(block_idx, counter, "c")
    nodes = [_decision_node(case_id, f"case({_truncate(expr, 20)})")]
    edges = []

    displayed = 0
    for arm_val, arm_stmt in arms[:4]:
        arm_val, arm_stmt = arm_val.strip(), arm_stmt.strip()
        if not arm_val or not arm_stmt:
            continue
        arm_nodes, arm_edges, arm_entry = _parse_body(arm_stmt, block_idx, counter, depth + 1, ctx)
        nodes += arm_nodes
        edges += arm_edges
        if arm_entry:
            edges.append({
                "id": f"e_{case_id}_{displayed}",
                "source": case_id,
                "target": arm_entry,
                "label": _truncate(arm_val, 12),
                "kind": "branch",
            })
        displayed += 1

    if len(arms) > 4:
        _mark_truncated(ctx, "case_arm_limit", len(arms) - 4)
        extra_id = _next_id(block_idx, counter, "p")
        nodes.append(_process_node(extra_id, f"({len(arms) - 4} more cases...)", kind="summary"))
        edges.append({"id": f"e_{case_id}_more", "source": case_id, "target": extra_id, "label": "...", "kind": "summary"})

    return nodes, edges, case_id


def _parse_case_arms_robust(case_body: str) -> list[tuple[str, str]]:
    """用 depth tracking 解析 case arms，正確處理 begin/end block 和三元運算子。"""
    arms = []
    s = case_body.strip()
    i = 0

    while i < len(s):
        while i < len(s) and s[i].isspace():
            i += 1
        if i >= len(s):
            break

        colon_pos = _find_top_level_colon(s, i)
        if colon_pos == -1:
            break

        arm_val = s[i:colon_pos].strip()
        i = colon_pos + 1

        while i < len(s) and s[i] in ' \t':
            i += 1

        if i < len(s) and re.match(r'^begin\b', s[i:], re.IGNORECASE):
            body_text, _ = _scan_begin_end(s[i:])
            i += len(body_text)
            arm_body = body_text
        else:
            sem_pos = s.find(';', i)
            if sem_pos == -1:
                arm_body = s[i:].strip()
                i = len(s)
            else:
                arm_body = s[i:sem_pos + 1].strip()
                i = sem_pos + 1

        if arm_val:
            arms.append((arm_val, arm_body))

    return arms


def _find_top_level_colon(s: str, start: int) -> int:
    depth = ternary = 0
    i = start
    while i < len(s):
        ch = s[i]
        if ch in 'bBeE':
            kw = re.match(r'\b(begin|end)\b', s[i:], re.IGNORECASE)
            if kw:
                depth += 1 if kw.group(1).lower() == 'begin' else -1
                i += len(kw.group(0))
                continue
        if ch == '?' and depth == 0:
            ternary += 1
        elif ch == ':' and depth == 0:
            if ternary > 0:
                ternary -= 1
            elif i == 0 or s[i - 1] not in '<>=!':
                return i
        i += 1
    return -1


# ─── assign 語句 ──────────────────────────────────────────────────────────────

def _find_assign_stmts(code: str) -> list[dict]:
    results = []
    pattern = re.compile(r'\bassign\s+((?:\{[^}]+\}|\w+)(?:\s*\[[^\]]+\])?)\s*=\s*(.+?);', re.DOTALL)
    for idx, m in enumerate(pattern.finditer(code)):
        output = m.group(1).strip()
        expression = m.group(2).strip()
        intent = _translate_assign_intent(output, expression)
        results.append({
            "id": f"as_{idx}",
            "output": output,
            "expression": _truncate(expression, 48),
            "input_signals": _signals_from_expr(expression),
            "intent_label": intent,
            "semantic_label": intent,
            "business_label": intent,
        })
    return results


# ─── 工具函式 ─────────────────────────────────────────────────────────────────

def _next_id(block_idx: int, counter: list, prefix: str) -> str:
    counter[0] += 1
    return f"ab_{block_idx}_{prefix}{counter[0]}"


def _truncate(s: str, max_len: int) -> str:
    s = ' '.join(s.split())
    return s if len(s) <= max_len else s[:max_len - 3] + '...'


def _line_number_at(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _base_signal(signal: str) -> str:
    return re.sub(r'\s*\[.*?\]\s*$', '', signal.strip())


def _signals_from_expr(expr: str) -> list[str]:
    keywords = {
        "if", "else", "case", "default", "begin", "end", "posedge", "negedge",
        "and", "or", "not",
    }
    signals = []
    for token in re.findall(r'\b[A-Za-z_][\w$]*\b', expr):
        if token.lower() in keywords:
            continue
        if re.fullmatch(r'[bBdDhHoO][0-9a-fA-F_xXzZ]+', token):
            continue
        signals.append(token)
    return sorted(set(signals))


def _collect_node_values(nodes: list[dict], key: str) -> list[str]:
    values = []
    for node in nodes:
        values.extend(node.get(key) or [])
    return sorted(set(values))


def _friendly_trigger(trigger: str, trigger_type: str) -> str:
    if trigger_type == "sequential":
        return "Clocked logic"
    if trigger in {"*", "always_comb"}:
        return "Combinational logic"
    return "Logic trigger"


def _friendly_condition(label: str) -> str:
    raw = label.strip()
    if raw.startswith("case("):
        inner = raw[5:-1] if raw.endswith(")") else raw[5:]
        if inner == "state":
            return "Current FSM state"
        return f"Select by {inner}"
    lower = raw.lower()
    if lower in {"rst", "reset", "reset_n", "rst_n"}:
        return "Reset active?"
    if raw.endswith("_valid"):
        return f"{raw} asserted?"
    if raw.endswith("_tick"):
        return f"{raw} occurred?"
    return raw if raw.endswith("?") else f"{raw}?"


def _friendly_process(label: str) -> str:
    if label == "(no change)":
        return "No state change"
    if label.startswith("[...]"):
        return "Summarized logic"
    if label.startswith("[loop:"):
        return "Loop summarized"
    return label


def _infer_block_role(nodes: list[dict], assigned_signals: list[str], trigger_type: str) -> str:
    decision_labels = [node.get("label", "") for node in nodes if node.get("type") == "decision"]
    assigned_set = set(assigned_signals)
    if (assigned_set & _FSM_STATE_NAMES) or any(
        label.startswith(_FSM_CASE_PREFIXES) for label in decision_labels
    ):
        return "fsm"
    if trigger_type == "combinational" and assigned_signals:
        return "output_decode"
    if trigger_type == "sequential":
        return "register_update"
    return "logic"


def _block_title(block_idx: int, _trigger: str, role: str) -> str:
    role_labels = {
        "fsm":             "流程狀態管理",
        "output_decode":   "輸出即時計算",
        "register_update": "資料定期更新",
        "logic":           "邏輯處理區塊",
    }
    label = role_labels.get(role, "邏輯處理區塊")
    if block_idx > 0:
        return f"{label} #{block_idx + 1}"
    return label


def _summarize_block(
    _trigger: str,
    _trigger_type: str,
    role: str,
    assigned_signals: list[str],
    condition_signals: list[str],
    nodes: list[dict],
) -> str:
    role_base = {
        "fsm":             "管理電路的狀態流程",
        "output_decode":   "根據輸入即時計算輸出",
        "register_update": "定期更新內部資料暫存器",
        "logic":           "執行邏輯運算",
    }
    base = role_base.get(role, "執行邏輯運算")

    if condition_signals:
        key_conds = _humanize_signals(condition_signals[:2])
        base += f"，根據{key_conds}決定行為"
    if assigned_signals:
        key_updates = _humanize_signals(assigned_signals[:2])
        base += f"，更新{key_updates}"

    if role == "fsm":
        states = _state_labels(nodes)
        if states:
            base += f"。包含 {', '.join(states[:4])} 等流程階段"

    return base + "。"


def _summarize_flowchart(always_blocks: list[dict], assign_blocks: list[dict]) -> str:
    role_name_map = {
        "fsm":             "狀態流程管理",
        "output_decode":   "輸出計算",
        "register_update": "資料更新",
        "logic":           "邏輯運算",
    }
    parts = []
    if always_blocks:
        roles: dict[str, int] = {}
        for block in always_blocks:
            r = block.get("block_role", "logic")
            roles[r] = roles.get(r, 0) + 1
        role_parts = []
        for role, count in roles.items():
            name = role_name_map.get(role, role)
            role_parts.append(f"{count} 個{name}區塊")
        parts.append("、".join(role_parts))
    if assign_blocks:
        count = len(assign_blocks)
        parts.append(f"{count} 個即時計算邏輯")
    if not parts:
        return "未偵測到邏輯區塊。"
    return "偵測到 " + "；".join(parts) + "。"


def _state_labels(nodes: list[dict]) -> list[str]:
    labels = []
    for node in nodes:
        label = node.get("label", "")
        m = re.match(r'state\s*(?:<=|=)\s*([A-Za-z_][\w$]*)', label)
        if m:
            labels.append(m.group(1))
    return sorted(set(labels))


def _build_state_diagram(always_blocks: list[dict]) -> dict | None:
    states = set()
    transitions = []
    for block in always_blocks:
        if block.get("block_role") != "fsm":
            continue
        node_by_id = {node["id"]: node for node in block.get("nodes", [])}
        adjacency: dict[str, list[str]] = {}
        for edge in block.get("edges", []):
            adjacency.setdefault(edge["source"], []).append(edge["target"])

        state_branch_edges = [
            edge for edge in block.get("edges", [])
            if edge.get("kind") == "branch" and edge.get("label") not in {"YES", "NO", "..."}
        ]
        for edge in state_branch_edges:
            src_state = edge.get("label")
            if not src_state:
                continue
            states.add(src_state)
            for target_id in _reachable_state_update_nodes(edge["target"], node_by_id, adjacency):
                label = node_by_id[target_id].get("label", "")
                m = re.match(r'state\s*(?:<=|=)\s*([A-Za-z_][\w$]*)', label)
                if not m:
                    continue
                dst = m.group(1)
                states.add(dst)
                transitions.append({"source": src_state, "target": dst, "label": label})
    if not states and not transitions:
        return None
    return {
        "states": sorted(states),
        "transitions": transitions,
        "summary": f"偵測到 {len(states)} 個狀態與 {len(transitions)} 條狀態轉換路徑。",
    }


def _reachable_state_update_nodes(start_id: str, node_by_id: dict, adjacency: dict[str, list[str]]) -> list[str]:
    found = []
    stack = [start_id]
    seen = set()
    while stack:
        node_id = stack.pop()
        if node_id in seen:
            continue
        seen.add(node_id)
        node = node_by_id.get(node_id, {})
        label = node.get("label", "")
        if re.match(r'state\s*(?:<=|=)\s*[A-Za-z_][\w$]*', label):
            found.append(node_id)
            continue
        stack.extend(adjacency.get(node_id, []))
    return found


# ─── 訊號依賴對照表 ───────────────────────────────────────────────────────────

def _build_signal_dependency_map(always_blocks: list[dict], assign_blocks: list[dict]) -> dict:
    dep_map: dict[str, dict] = {}

    def _ensure(sig: str) -> None:
        if sig not in dep_map:
            dep_map[sig] = {"written_by": [], "read_by": []}

    for block in always_blocks:
        block_id = block["id"]
        for sig in block.get("assigned_signals", []):
            _ensure(sig)
            if block_id not in dep_map[sig]["written_by"]:
                dep_map[sig]["written_by"].append(block_id)
        for sig in block.get("condition_signals", []):
            _ensure(sig)
            if block_id not in dep_map[sig]["read_by"]:
                dep_map[sig]["read_by"].append(block_id)

    for assign in assign_blocks:
        assign_id = assign["id"]
        output = _base_signal(assign.get("output", ""))
        if output:
            _ensure(output)
            if assign_id not in dep_map[output]["written_by"]:
                dep_map[output]["written_by"].append(assign_id)
        for sig in assign.get("input_signals", []):
            _ensure(sig)
            if assign_id not in dep_map[sig]["read_by"]:
                dep_map[sig]["read_by"].append(assign_id)

    return dep_map


# ─── 測試入口 ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "../sample_verilog/counter_4bit.v"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    print(json.dumps(extract_flowchart(content), ensure_ascii=False, indent=2))
