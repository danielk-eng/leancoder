"""Prompts. Kept short on purpose: every prompt token is billed on every call."""

LEAN_SYS = (
    "You fix bugs in a Python repo. You are given the failing test, the failure and the relevant code. "
    "Reply ONLY with edit blocks, no explanation:\n"
    "<<<<<<< SEARCH path/to/file.py\n<exact existing lines>\n=======\n<replacement lines>\n>>>>>>> REPLACE\n"
    "Example reply:\n<<<<<<< SEARCH app/util.py\n    return a - b\n=======\n    return a + b\n>>>>>>> REPLACE\n"
    "Keep SEARCH minimal but unique and copy it exactly from CODE (without the line-number prefixes). "
    "Do not repeat unchanged code, no headings, no prose. Never edit tests. Prefer current, non-deprecated library APIs."
)

BASELINE_SYS = (
    "You are a coding agent. Fix the bug so the tests pass. Reply with the COMPLETE new content of every file "
    "you change, each in a block:\n### FILE: path/to/file.py\n```python\n<entire file>\n```\n"
    "Do not edit tests."
)
