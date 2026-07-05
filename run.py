"""Entry point for Touchline RPG.

Kept as a thin shim so a packaged console-script entry point can call the same
``main()`` without depending on this file. Run with ``python run.py``.
"""

from touchline.desktop.launcher import main

if __name__ == "__main__":
    main()
