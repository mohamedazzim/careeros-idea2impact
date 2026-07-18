import pytest
import sys
import os

if __name__ == "__main__":
    os.environ["MOCK_RETRIEVAL_AGENT"] = "true"
    os.environ["MOCK_EVAL"] = "true"
    sys.exit(pytest.main(["-v", "backend/tests/test_orchestration.py"]))
