from pathlib import Path
import json, re
ROOT = Path(__file__).resolve().parents[1]
queries = json.loads((ROOT/'retrieval_validation/test_queries.json').read_text(encoding='utf-8'))
docs = {p.name:p.read_text(encoding='utf-8', errors='ignore') for p in ROOT.glob('*.md')}
def tok(s): return set(re.findall(r'[a-z0-9_]+', s.lower()))
results=[]
for item in queries:
    qt=tok(item['question'])
    ranked=sorted(((len(qt & tok(text))/max(1,len(qt)), name) for name,text in docs.items()), reverse=True)[:5]
    hit=any(name in item['expected_docs'] for score,name in ranked)
    results.append({'question':item['question'],'category':item['category'],'expected_docs':item['expected_docs'],'top_docs':[{'doc':n,'score':round(s,3)} for s,n in ranked],'hit':hit})
summary={'total':len(results),'hits':sum(1 for r in results if r['hit']),'hit_rate':round(sum(1 for r in results if r['hit'])/max(1,len(results)),3)}
(ROOT/'retrieval_validation/retrieval_results.json').write_text(json.dumps({'summary':summary,'results':results}, indent=2), encoding='utf-8')
(ROOT/'retrieval_validation/RETRIEVAL_VALIDATION_REPORT.md').write_text('# Retrieval Validation Report\n\nLexical smoke test over docs/rag_v2. This does not call Qdrant or embedding providers.\n\n' + f"- Total queries: {summary['total']}\n- Hits: {summary['hits']}\n- Hit rate: {summary['hit_rate']}\n", encoding='utf-8')
print(json.dumps(summary))
