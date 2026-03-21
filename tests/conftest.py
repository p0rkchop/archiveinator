from __future__ import annotations

import os


# Disable Rich/Typer ANSI formatting in test output so assertions
# can match plain text (e.g. "--output-dir" without escape sequences).
os.environ["NO_COLOR"] = "1"
