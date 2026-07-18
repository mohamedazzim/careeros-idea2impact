import os, re

patterns = [
    (r'MOCK_', 'MOCK_ENV'),
    (r'mock_', 'mock_func'),
    (r'fake_', 'fake'),
    (r'stub_', 'stub'),
    (r'\bplaceholder\b', 'placeholder'),
    (r'\bTODO\b', 'TODO'),
    (r'\bFIXME\b', 'FIXME'),
    (r'NotImplementedError', 'not_implemented'),
    (r'dummy_vector', 'dummy_vector'),
    (r'mock_key', 'mock_key'),
    (r'emulated|simulated|synthetic', 'synthetic'),
    (r'\bpass\s*$', 'bare_pass'),
    (r'return\s*\{\}\s*$', 'empty_return'),
    (r'#\s*(Removed|Disabled|Stub)', 'removed_comment'),
]

matches = []
for root, dirs, files in os.walk('D:\\StrangerThings Season 5\\aiStudio-main\\aiStudio-main\\backend\\src'):
    for f in files:
        if not f.endswith('.py'):
            continue
        fpath = os.path.join(root, f)
        try:
            with open(fpath, encoding='utf-8') as fh:
                lines = fh.readlines()
                in_triple = False
                for lineno, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        in_triple = not in_triple
                    if in_triple:
                        continue
                    if stripped.startswith('#'):
                        continue
                    for pat, cat in patterns:
                        if re.search(pat, stripped):
                            if cat == 'bare_pass' and (stripped.endswith('...') or 'def ' in lines[lineno-2] if lineno>=2 else False):
                                continue
                            matches.append((fpath, lineno, cat, stripped[:130]))
                            break
        except:
            pass

for fpath, lineno, cat, line in sorted(matches, key=lambda x: x[2]):
    rel = fpath.split('backend\\src\\')[-1] if 'backend\\src\\' in fpath else fpath
    print(f'{rel}:{lineno} [{cat}] {line}')
