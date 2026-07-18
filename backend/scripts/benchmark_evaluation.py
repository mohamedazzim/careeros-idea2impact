import asyncio
import os
import time
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.evaluation.evaluation_engine import evaluation_engine

datasets = [
    {
        "name": "Strong Resume vs Matching Job",
        "resume": "Senior React Engineer with 10 years experience. Built massive scalable UIs.",
        "job": "Looking for Senior React Engineer to lead frontend.",
        "context": "[1] Resume chunk: Senior React Engineer\n[2] Job chunk: Need React leader"
    },
    {
        "name": "Weak Resume vs Matching Job",
        "resume": "Junior dev. Know some HTML.",
        "job": "Looking for Senior React Engineer to lead frontend.",
        "context": "[1] Resume chunk: Junior dev\n[2] Job chunk: Need React leader"
    },
    {
        "name": "Strong Resume vs Unrelated Job",
        "resume": "Senior React Engineer with 10 years experience. Unrelated.",
        "job": "Looking for Medical Doctor. Must have MD.",
        "context": "[1] Resume chunk: React Engineer. Unrelated\n[2] Job chunk: Medical doctor MD"
    },
    {
        "name": "Partial Match Resume vs Job",
        "resume": "Backend Engineer. Know Python and basic JS.",
        "job": "Fullstack engineer. Python, React, AWS.",
        "context": "[1] Resume chunk: Python and basic JS\n[2] Job chunk: Fullstack Python React"
    }
]

async def run_benchmark():
    os.environ["MOCK_EVAL"] = "true"
    print("--- Running Evaluation Dataset Validation ---")
    
    for ds in datasets:
        print(f"\nEvaluating: {ds['name']}")
        start = time.time()
        result = await evaluation_engine.evaluate(ds["resume"], ds["job"], ds["context"])
        elapsed = time.time() - start
        
        eval_dict = result["evaluation"]
        print(f"  ATS Score: {eval_dict['ats_score']['score']}")
        print(f"  Match Score: {eval_dict['match_score']['score']}")
        print(f"  Strengths found: {len(eval_dict['strengths'])}")
        print(f"  Weaknesses found: {len(eval_dict['weaknesses'])}")
        print(f"  Time: {elapsed * 1000:.2f}ms")

if __name__ == "__main__":
    asyncio.run(run_benchmark())
