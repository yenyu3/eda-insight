"""utils/graph_utils.py — Module dependency DAG 分析（使用 NetworkX）。"""

try:
    import networkx as nx
except ImportError:
    nx = None


def build_dag(parser_result: dict) -> dict:
    """
    從 verilog_parser 的解析結果建立 Module dependency DAG。

    Returns:
        D3.js-compatible dict:
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
            if inst not in G:
                G.add_node(inst)
            G.add_edge(module["name"], inst)

    return {
        "nodes": [{"id": n, "in_degree": G.in_degree(n)} for n in G.nodes],
        "links": [{"source": u, "target": v} for u, v in G.edges],
        "critical_path": _safe_longest_path(G),
        "topological_order": _safe_topological_sort(G),
    }


def get_bottleneck_nodes(dag_result: dict) -> list[str]:
    """回傳 critical path 上所有節點（潛在瓶頸）。"""
    return dag_result.get("critical_path", [])


def _safe_longest_path(G) -> list[str]:
    try:
        return list(nx.dag_longest_path(G))
    except nx.NetworkXUnfeasible:
        return []


def _safe_topological_sort(G) -> list[str]:
    try:
        return list(nx.topological_sort(G))
    except nx.NetworkXUnfeasible:
        return sorted(G.nodes, key=lambda n: G.in_degree(n))
