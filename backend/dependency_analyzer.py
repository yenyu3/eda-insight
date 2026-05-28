"""
dependency_analyzer.py — Module 依賴關係分析模組

使用 networkx 建立 Module 間的有向無環圖（DAG），
計算 critical path、topological order，並輸出 D3.js force graph 格式。
"""

import json

try:
    import networkx as nx
except ImportError:
    nx = None


def build_dag(parser_result: dict) -> dict:
    """
    從 verilog_parser 的解析結果建立 DAG，回傳 D3.js-compatible dict。

    回傳格式：
    {
        "nodes": [{"id": str, "in_degree": int}],
        "links": [{"source": str, "target": str}],
        "critical_path": [str],
        "topological_order": [str]
    }
    """
    if nx is None:
        raise ImportError("networkx 套件未安裝，請執行 pip install networkx")

    G = nx.DiGraph()

    for module in parser_result.get("modules", []):
        G.add_node(module["name"])
        for inst in module.get("instantiations", []):
            # 若被例化的模組還沒在圖中，先加進去
            if inst not in G:
                G.add_node(inst)
            G.add_edge(module["name"], inst)

    critical_path = _safe_longest_path(G)
    topo_order = _safe_topological_sort(G)

    return {
        "nodes": [{"id": n, "in_degree": G.in_degree(n)} for n in G.nodes],
        "links": [{"source": u, "target": v} for u, v in G.edges],
        "critical_path": critical_path,
        "topological_order": topo_order,
    }


def _safe_longest_path(G) -> list[str]:
    """
    計算 DAG 最長路徑（critical path）。
    若圖中有環（不符合 DAG 定義）則回傳空清單。
    """
    try:
        return list(nx.dag_longest_path(G))
    except nx.NetworkXUnfeasible:
        return []


def _safe_topological_sort(G) -> list[str]:
    """
    拓撲排序。若圖中有環則回傳按 in_degree 排序的節點清單作為 fallback。
    """
    try:
        return list(nx.topological_sort(G))
    except nx.NetworkXUnfeasible:
        return sorted(G.nodes, key=lambda n: G.in_degree(n))


def get_bottleneck_nodes(dag_result: dict) -> list[str]:
    """
    找出 critical path 上的節點（瓶頸節點）。
    critical path 上的每個節點都是潛在的最佳化目標。
    """
    return dag_result.get("critical_path", [])


# ---------- 測試入口 ----------

if __name__ == "__main__":
    import sys
    sys.path.insert(0, ".")
    from verilog_parser import parse_verilog

    path = sys.argv[1] if len(sys.argv) > 1 else "../sample_verilog/counter_4bit.v"
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    parsed = parse_verilog(content)
    dag = build_dag(parsed)
    print(json.dumps(dag, ensure_ascii=False, indent=2))
