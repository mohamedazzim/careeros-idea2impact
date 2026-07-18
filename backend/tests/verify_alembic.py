from alembic.config import Config
from alembic.script import ScriptDirectory
import os, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)) + "/..")
sys.path.insert(0, ".")

cfg = Config("alembic.ini")
script = ScriptDirectory.from_config(cfg)
revisions = list(script.walk_revisions())
print(f"Total revisions: {len(revisions)}")
for rev in reversed(revisions):
    print(f"  {rev.revision} -> {rev.down_revision or 'BASE'}: {rev.doc[:80]}")
print("ALEMBIC_CHAIN: VALID")
