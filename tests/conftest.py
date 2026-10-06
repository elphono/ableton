import os
import sys

# The tools are standalone scripts at the repository root, not a package.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
