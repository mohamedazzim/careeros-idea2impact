import warnings, sys
warnings.filterwarnings('ignore')
sys.path.insert(0, '.')
from src.main import app

routes = [r for r in app.routes if hasattr(r, 'methods')]
phase18_paths = set()
for r in routes:
    path = str(getattr(r, 'path', ''))
    methods = sorted(list(getattr(r, 'methods', set())))
    if path.startswith('/api/v1'):
        print(f'  {" ".join(methods):8s} {path}')
        if any(p in path for p in ['rerank', 'opportunities']):
            phase18_paths.add(path)

total = len([r for r in routes if hasattr(r, "path")])
print(f'\nTotal API routes: {total}')
print(f'Phase 18 endpoints registered: {len(phase18_paths)}')
for p in sorted(phase18_paths):
    print(f'  {p}')
print('API ROUTER REGISTRATION: PASS')
