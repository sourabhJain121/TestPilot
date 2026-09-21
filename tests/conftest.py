import os
import warnings

# Suppress deprecation warnings from third-party async/chromadb/starlette libraries
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Ensure CI mode / offline mode is default for pytest runs so tests never hang on remote sockets
os.environ.setdefault("TESTPILOT_CI_MODE", "true")
