"""
Pytest configuration and global warning filters for TestPilot AI.
"""

import warnings

# Suppress deprecation warnings from third-party async/chromadb/starlette libraries
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
