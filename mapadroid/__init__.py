import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.realpath(__file__)))

path = Path(__file__)
MAD_ROOT = path.parent.parent
