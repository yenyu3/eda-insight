try:
    import networkx as nx
except ImportError:
    nx = None


def build_dag(parser_result: dict) -> dict:
    """
    從 verilog_parser 的解析結果建立 module instantiation DAG。

    約定：
    - parser_result["modules"] 中每個 module 包含：
      - name: module 名稱
      - instantiations: 此 module 所 instantiate 的下層 module 名稱列表

    圖的方向定義為：parent module → 被 instantiate 的 sub-module。
    因此 in_degree=0 的節點代表頂層 module（未被任何其他 module instantiate），
    前端以此判斷根節點（顯示藍色）。

    回傳結構：
    {
        "nodes": [{"id": str, "in_degree": int}],
        "links": [{"source": str, "target": str}],
        "critical_path": [str],
        "topological_order": [str],
        "has_cycle": bool
    }
    """
    if nx is None:
        raise ImportError("networkx 套件未安裝，請執行 pip install networkx")

    G = nx.DiGraph()

    for module in parser_result.get("modules", []):
        module_name = module.get("name")
        if not module_name:
            continue

        G.add_node(module_name)

        # instantiations 內容為被 instantiate 的 module 名稱
        for inst in module.get("instantiations", []):
            if not inst:
                continue
            G.add_node(inst)
            G.add_edge(module_name, inst)

    has_cycle = not nx.is_directed_acyclic_graph(G)

    return {
        "nodes": [{"id": n, "in_degree": G.in_degree(n)} for n in G.nodes],
        "links": [{"source": u, "target": v} for u, v in G.edges],
        "critical_path": _safe_longest_path(G),
        "topological_order": _safe_topological_sort(G),
        "has_cycle": has_cycle,
    }


def get_bottleneck_nodes(dag_result: dict) -> list[str]:
    """回傳 critical path 上所有節點（潛在瓶頸）。"""
    return dag_result.get("critical_path", [])


def _safe_longest_path(G) -> list[str]:
    """
    回傳 DAG 的最長路徑。

    若圖中存在 cycle，則回傳空陣列，避免 NetworkX 拋例外中斷流程。
    """
    try:
        return list(nx.dag_longest_path(G))
    except nx.NetworkXUnfeasible:
        return []


def _safe_topological_sort(G) -> list[str]:
    """
    回傳拓樸排序結果。

    若圖中存在 cycle，則改用 in_degree 作為近似排序；
    這不是嚴格的拓樸順序，只作為 fallback 顯示用途。
    """
    try:
        return list(nx.topological_sort(G))
    except nx.NetworkXUnfeasible:
        return sorted(G.nodes, key=lambda n: G.in_degree(n))
