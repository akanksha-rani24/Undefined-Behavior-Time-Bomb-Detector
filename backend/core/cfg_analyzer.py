"""
CFG (Control Flow Graph) builder from LLVM IR.
Uses NetworkX for graph analysis and produces serializable node/edge data.
"""
import re
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from core.ir_analyzer import IRFunction, parse_ir_functions
from models.schemas import CFGData, CFGEdge, CFGNode


def build_cfg_from_function(func: IRFunction, opt: str) -> nx.DiGraph:
    """Build a NetworkX DiGraph from a parsed IR function."""
    G = nx.DiGraph()

    for name, block in func.blocks.items():
        G.add_node(name, label=_block_label(name, block), opt=opt, func=func.name)

    for name, block in func.blocks.items():
        term = block.terminator
        if not term:
            continue
        # Conditional branch
        m = re.search(r'\bbr\s+i1\s+[^,]+,\s*label\s+%?(\w+),\s*label\s+%?(\w+)', term)
        if m:
            G.add_edge(name, m.group(1), kind="branch", label="true")
            G.add_edge(name, m.group(2), kind="branch", label="false")
            continue
        # Unconditional branch
        m2 = re.search(r'\bbr\s+label\s+%?(\w+)', term)
        if m2:
            G.add_edge(name, m2.group(1), kind="fallthrough")
            continue
        # Switch
        for sm in re.finditer(r'label\s+%?(\w+)', term):
            G.add_edge(name, sm.group(1), kind="switch")

    return G


def _block_label(name: str, block) -> str:
    n_instr = len(block.instructions)
    term = block.terminator.split(" ")[0] if block.terminator else "?"
    return f"{name}\n({n_instr} instr, {term})"


def build_cfg_data(o0_ir: str, o2_ir: str, func_name: Optional[str] = None) -> CFGData:
    """
    Build CFGData for all (or a specific) function comparing O0 vs O2.
    When func_name is None, picks the first non-main user function.
    """
    f0_all = parse_ir_functions(o0_ir)
    f2_all = parse_ir_functions(o2_ir)

    # Pick the most interesting function
    if func_name and func_name in f0_all:
        f0 = f0_all[func_name]
        f2 = f2_all.get(func_name)
    else:
        # Pick function with most block changes
        best = None
        best_diff = 0
        for name, f in f0_all.items():
            if name.startswith("__") or name == "main":
                continue
            f2_candidate = f2_all.get(name)
            if f2_candidate:
                diff = abs(f.block_count - f2_candidate.block_count)
                if diff > best_diff or best is None:
                    best_diff = diff
                    best = name
        if best:
            f0 = f0_all[best]
            f2 = f2_all.get(best)
        elif f0_all:
            name = next(iter(f0_all))
            f0 = f0_all[name]
            f2 = f2_all.get(name)
        else:
            return CFGData()

    G0 = build_cfg_from_function(f0, "o0")
    o0_nodes = [
        CFGNode(id=n, label=d.get("label", n), kind=_node_kind(n, G0), opt="o0")
        for n, d in G0.nodes(data=True)
    ]
    o0_edges = [
        CFGEdge(source=u, target=v, kind=d.get("kind", "branch"))
        for u, v, d in G0.edges(data=True)
    ]

    if f2:
        G2 = build_cfg_from_function(f2, "o2")
        o2_nodes = [
            CFGNode(id=n, label=d.get("label", n), kind=_node_kind(n, G2), opt="o2")
            for n, d in G2.nodes(data=True)
        ]
        o2_edges = [
            CFGEdge(source=u, target=v, kind=d.get("kind", "branch"))
            for u, v, d in G2.edges(data=True)
        ]
        o0_ids = {n.id for n in o0_nodes}
        o2_ids = {n.id for n in o2_nodes}
        eliminated = list(o0_ids - o2_ids)
        added = list(o2_ids - o0_ids)
    else:
        o2_nodes, o2_edges = [], []
        eliminated, added = list(G0.nodes()), []

    return CFGData(
        o0_nodes=o0_nodes, o0_edges=o0_edges,
        o2_nodes=o2_nodes, o2_edges=o2_edges,
        eliminated_nodes=eliminated, added_nodes=added,
    )


def _node_kind(name: str, G: nx.DiGraph) -> str:
    if G.in_degree(name) == 0:
        return "entry"
    if G.out_degree(name) == 0:
        return "exit"
    return "block"


def count_back_edges(G: nx.DiGraph) -> int:
    """Count back-edges (loop indicators) using DFS."""
    try:
        return len(list(nx.simple_cycles(G)))
    except Exception:
        return 0
