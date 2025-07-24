import sys
import os

# Adjust sys.path to ensure `main.py` (located in the project root) can be imported.
# This makes `python -m spotlight_gui` work by finding `main.py` one level up.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Now, import and run the main GUI function from the project root's main.py
from main import run_gui

if __name__ == '__main__':
    run_gui()