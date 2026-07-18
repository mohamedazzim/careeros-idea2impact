#!/usr/bin/env python3
"""
CareerOS Documentation Drift Prevention Script

Verifies that documentation counts match actual codebase.
Run from project root: python scripts/docs/verify_counts.py

This script is for documentation maintenance only.
It does NOT modify runtime application behavior.
"""
import os
import re
import glob
from datetime import datetime, timezone
from pathlib import Path


def count_agents(backend_src: str) -> int:
    """Count agent files in backend/src/agents/ (top-level agents only).

    Documentation tracks the 11 registered core agents in this package.
    Service-level agents, such as OutcomeIntelligenceAgent, are documented
    separately and are not part of this core count.
    """
    agents_dir = os.path.join(backend_src, "agents")
    count = 0
    if os.path.isdir(agents_dir):
        for f in os.listdir(agents_dir):
            if f.endswith(".py") and f != "__init__.py" and not f.startswith("_"):
                count += 1
    return count


def count_graphs(backend_src: str) -> int:
    """Count LangGraph graph files in graphs/ and services/orchestration/graph.py"""
    count = 0
    graphs_dir = os.path.join(backend_src, "graphs")
    if os.path.isdir(graphs_dir):
        for f in os.listdir(graphs_dir):
            if f.endswith(".py") and f != "__init__.py" and not f.startswith("_"):
                count += 1
    # Check for orchestration graph
    orch_graph = os.path.join(backend_src, "services", "orchestration", "graph.py")
    if os.path.isfile(orch_graph):
        count += 1
    return count


def count_routers(main_py: str) -> int:
    """Count include_router calls in main.py"""
    if not os.path.isfile(main_py):
        return -1
    with open(main_py, "r", encoding="utf-8") as f:
        content = f.read()
    return len(re.findall(r"app\.include_router\(", content))


def find_llm_model(gemini_py: str) -> str:
    """Extract Gemini model name from gemini_provider.py"""
    if not os.path.isfile(gemini_py):
        return "UNKNOWN"
    with open(gemini_py, "r", encoding="utf-8") as f:
        for line in f:
            if "model" in line and "gemini" in line.lower() and "=" in line:
                match = re.search(r'"(gemini-[^"]+)"', line)
                if match:
                    return match.group(1)
    return "UNKNOWN"


def find_embedding_model(nvembed_py: str) -> str:
    """Extract embedding model name from nvembed_service.py"""
    if not os.path.isfile(nvembed_py):
        return "UNKNOWN"
    with open(nvembed_py, "r", encoding="utf-8") as f:
        for line in f:
            if "model_name" in line and "=" in line:
                match = re.search(r'"(nvidia/[^"]+)"', line)
                if match:
                    return match.group(1)
    return "UNKNOWN"


def find_deepseek_model(config_py: str) -> str:
    """Extract DeepSeek model from config.py"""
    if not os.path.isfile(config_py):
        return "UNKNOWN"
    with open(config_py, "r", encoding="utf-8") as f:
        for line in f:
            if "DEEPSEEK_MODEL" in line and "=" in line:
                match = re.search(r'"([^"]+)"', line.split("=")[1])
                if match:
                    return match.group(1)
    return "UNKNOWN"


def check_doc_value(filepath: str, pattern: str) -> list:
    """Check if a documentation file contains a specific value"""
    results = []
    if not os.path.isfile(filepath):
        return results
    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            if re.search(pattern, line):
                results.append((i, line.strip()))
    return results


def main():
    # Determine paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", ".."))
    backend_src = os.path.join(project_root, "backend", "src")
    main_py = os.path.join(backend_src, "main.py")
    gemini_py = os.path.join(backend_src, "services", "llm", "gemini_provider.py")
    nvembed_py = os.path.join(backend_src, "services", "embedding", "nvembed_service.py")
    config_py = os.path.join(backend_src, "core", "config.py")
    docs_dir = os.path.join(project_root, "docs")

    # Get actual counts
    actual_agents = count_agents(backend_src)
    actual_graphs = count_graphs(backend_src)
    actual_routers = count_routers(main_py)
    actual_gemini_model = find_llm_model(gemini_py)
    actual_embedding = find_embedding_model(nvembed_py)
    actual_deepseek = find_deepseek_model(config_py)

    # Expected values from documentation
    expected = {
        "agents": 11,
        "graphs": 4,
        "routers": 29,
        "gemini_model": "gemini-2.5-flash",
        "embedding": "nvidia/nv-embed-v1",
        "deepseek_model": "meta/llama-3.3-70b-instruct",
    }

    # Actual values
    actual = {
        "agents": actual_agents,
        "graphs": actual_graphs,
        "routers": actual_routers,
        "gemini_model": actual_gemini_model,
        "embedding": actual_embedding,
        "deepseek_model": actual_deepseek,
    }

    # Check documentation for mismatches
    doc_files = glob.glob(os.path.join(docs_dir, "**", "*.md"), recursive=True)
    mismatches = []

    # Check agent count in docs
    for df in doc_files:
        results = check_doc_value(df, r"\b1[12]\s+agent")
        for line_num, line_text in results:
            if "11 agent" in line_text and actual_agents != 11:
                mismatches.append(f"  {os.path.basename(df)}:{line_num}: says 11 agents, actual is {actual_agents}")
            elif "12 agent" in line_text and actual_agents != 12:
                mismatches.append(f"  {os.path.basename(df)}:{line_num}: says 12 agents, actual is {actual_agents}")

    # Check graph count in docs
    for df in doc_files:
        results = check_doc_value(df, r"\b[34]\s+graph")
        for line_num, line_text in results:
            if "3 graph" in line_text and actual_graphs == 4:
                mismatches.append(f"  {os.path.basename(df)}:{line_num}: says 3 graphs, actual is {actual_graphs}")
            elif "4 graph" in line_text and actual_graphs != 4:
                mismatches.append(f"  {os.path.basename(df)}:{line_num}: says 4 graphs, actual is {actual_graphs}")

    # Check router count in docs
    for df in doc_files:
        results = check_doc_value(df, r"\b19\s+router")
        for line_num, line_text in results:
            if "19 router" in line_text:
                mismatches.append(f"  {os.path.basename(df)}:{line_num}: says 19 routers, actual is {actual_routers}")

    # Check NV-Embed version in docs
    for df in doc_files:
        results = check_doc_value(df, r"NV-Embed-v2")
        for line_num, line_text in results:
            mismatches.append(f"  {os.path.basename(df)}:{line_num}: says NV-Embed-v2, should be NV-Embed-v1")

    # Generate report
    timestamp = datetime.now(timezone.utc).isoformat()
    report_lines = [
        "# Runtime Counts — Documentation Drift Prevention",
        "",
        f"**Generated**: {timestamp}",
        f"**Script**: `scripts/docs/verify_counts.py`",
        "",
        "---",
        "",
        "## Actual Counts (from codebase)",
        "",
        f"| Property | Actual Value |",
        f"|----------|-------------|",
        f"| Agents | {actual_agents} |",
        f"| Graphs | {actual_graphs} |",
        f"| Routers | {actual_routers} |",
        f"| Gemini Model | `{actual_gemini_model}` |",
        f"| Embedding Model | `{actual_embedding}` |",
        f"| DeepSeek Model | `{actual_deepseek}` |",
        "",
        "## Expected Counts (from documentation)",
        "",
        f"| Property | Expected | Actual | Status |",
        f"|----------|----------|--------|--------|",
    ]

    all_pass = True
    for key in expected:
        exp = expected[key]
        act = actual[key]
        status = "PASS" if exp == act else "FAIL"
        if status == "FAIL":
            all_pass = False
        report_lines.append(f"| {key} | {exp} | {act} | {status} |")

    report_lines.extend([
        "",
        "## Documentation Mismatches",
        "",
    ])

    if mismatches:
        for m in mismatches:
            report_lines.append(m)
    else:
        report_lines.append("None found.")

    report_lines.extend([
        "",
        f"## Overall Status: {'ALL PASS' if all_pass and not mismatches else 'MISMATCHES FOUND'}",
        "",
    ])

    report = "\n".join(report_lines)

    print(report)


if __name__ == "__main__":
    main()
