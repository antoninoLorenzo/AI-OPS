"""
https://github.com/Silleellie/pylint-github-action
"""
import os.path
import re
import sys

README_PATH = sys.argv[1]
NUMERIC_SCORE = sys.argv[2]
BADGE_TEXT = sys.argv[3]
BADGE_COLOR = sys.argv[4]

if not os.path.isfile(README_PATH):
    raise FileNotFoundError(f"README.md path is wrong, no file can be located at {README_PATH}")

with open(README_PATH, "r", encoding="utf8") as f:
    content = f.read()

query = f"{BADGE_TEXT}-{NUMERIC_SCORE}-{BADGE_COLOR}?logo=python&logoColor=white"
badge_url = f"https://img.shields.io/badge/{query}"

patt = r"(?<=!\[pylint]\()(.*?)(?=\))"
if re.search(patt, content) is None:
    raise ValueError("Pylint badge not found! Be sure to put an empty one which acts as a placeholder "
                     "if this is your first run. Check README.md for examples!")

result = re.sub(patt, badge_url, content)
with open(README_PATH, "w", encoding="utf8") as f:
    f.write(result)
