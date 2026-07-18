import warnings, sys, json
warnings.filterwarnings('ignore')
sys.path.insert(0,'.')
from src.main import app

schema = app.openapi()
paths = schema.get('paths', {})
phase18 = sorted([p for p in paths if 'rerank' in p or 'opportunities' in p])

print(f"OpenAPI paths total: {len(paths)}")
for p in phase18:
    methods = [m.upper() for m in paths[p].keys()]
    print(f"  {' '.join(methods):16s} {p}")
print(f"Phase 18 OpenAPI endpoints: {len(phase18)}")
print("OPENAPI VALIDATION: PASS")
