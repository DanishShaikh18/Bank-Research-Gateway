import json
from google.adk.evaluation.local_eval_sets_manager import EvalSet
print(json.dumps(EvalSet.model_json_schema(), indent=2))
