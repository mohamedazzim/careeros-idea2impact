import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.services.orchestration.graph import build_orchestrator_graph

def export_visualization():
    graph = build_orchestrator_graph()
    
    # Generate mermaid
    try:
        mermaid_code = graph.get_graph().draw_mermaid()
        
        with open("ORCHESTRATION_GRAPH.md", "w") as f:
            f.write("# CareerOS Orchestration Graph\\n\\n")
            f.write("```mermaid\\n")
            f.write(mermaid_code)
            f.write("\\n```\\n")
        print("Successfully generated ORCHESTRATION_GRAPH.md")
    except Exception as e:
        print(f"Failed to generate visualization: {e}")

if __name__ == "__main__":
    export_visualization()
