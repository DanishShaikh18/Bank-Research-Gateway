import json

with open("evals/routing.evalset.json", "r") as f:
    data = json.load(f)

for case in data:
    for inv in case["data"]:
        if "expected_tool_trajectory" in inv:
            tools = inv.pop("expected_tool_trajectory")
            new_tools = []
            for t in tools:
                new_tools.append({
                    "tool_name": t["tool_name"],
                    "tool_input": {}
                })
            inv["expected_tool_use"] = new_tools

with open("evals/routing.evalset.json", "w") as f:
    json.dump(data, f, indent=2)
