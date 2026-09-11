import json
import sys
import os

# Add the parent directory to sys.path so we can import app
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.privacy import detect_sensitive_spans, TokenVault, sanitize_input, inspect_outbound_payload

def run_eval():
    print("Running Privacy Evaluation...")
    cases_path = os.path.join(os.path.dirname(__file__), 'pii_cases.jsonl')
    
    total_entities = 0
    detected_entities = 0
    correct_detections = 0
    leakage_failures = 0
    
    with open(cases_path, 'r') as f:
        for line in f:
            if not line.strip(): continue
            case = json.loads(line)
            
            text = case['text']
            expected_entities = case['entities']
            
            # 1. Detection Evaluation
            spans = detect_sensitive_spans(text)
            
            expected_values = [e['value'] for e in expected_entities]
            detected_values = [s.value for s in spans]
            
            total_entities += len(expected_values)
            detected_entities += len(detected_values)
            
            for v in detected_values:
                if v in expected_values:
                    correct_detections += 1
                    
            # 2. Outbound Leakage Evaluation
            vault = TokenVault()
            sanitized = sanitize_input(text, vault)
            
            # Check if any expected entity is still in the sanitized text
            for e in expected_entities:
                if e['value'] in sanitized:
                    print(f"LEAKAGE DETECTED in case {case['id']}: {e['value']}")
                    leakage_failures += 1
            
            # Check outbound inspector
            safe, _ = inspect_outbound_payload(sanitized, vault)
            if not safe:
                # Our inspector should say it's safe because we just sanitized it
                print(f"FALSE POSITIVE BLOCK in case {case['id']}")
                
    precision = correct_detections / detected_entities if detected_entities else 1.0
    recall = correct_detections / total_entities if total_entities else 1.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) else 0.0
    
    print(f"Total Expected Entities: {total_entities}")
    print(f"Total Detected Entities: {detected_entities}")
    print(f"Precision: {precision:.2f}")
    print(f"Recall: {recall:.2f}")
    print(f"F1 Score: {f1:.2f}")
    print(f"Outbound Leakage Rate: {leakage_failures / total_entities if total_entities else 0.0:.2%}")
    
    assert leakage_failures == 0, "Outbound leakage test failed!"
    print("Privacy Evaluation Passed!")

if __name__ == "__main__":
    run_eval()
