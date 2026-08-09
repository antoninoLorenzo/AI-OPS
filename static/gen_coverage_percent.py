import json

try:
    with open("static/ai-ops-coverage.json") as fp:
        raw_data = json.load(fp)
    print(f'{raw_data["totals"]["percent_covered"]:.0f}')
except FileNotFoundError:
    print("unk")

