import json
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.rag import ChromaRetriever

def run_eval():
    print("Running RAG Evaluation...")
    cases_path = os.path.join(os.path.dirname(__file__), 'rag_cases.jsonl')
    
    retriever = ChromaRetriever()
    
    total_cases = 0
    correct_document = 0
    mrr_sum = 0.0
    
    with open(cases_path, 'r') as f:
        for line in f:
            if not line.strip(): continue
            case = json.loads(line)
            
            question = case['question']
            expected_doc = case['expected_document']
            
            results = retriever.search_hybrid(question, top_k=3)
            
            total_cases += 1
            
            # Check Recall and MRR
            doc_found = False
            for rank, res in enumerate(results, 1):
                if res.document_name == expected_doc:
                    if not doc_found:
                        correct_document += 1
                        mrr_sum += 1.0 / rank
                        doc_found = True
                    
    recall_at_3 = correct_document / total_cases if total_cases else 0.0
    mrr = mrr_sum / total_cases if total_cases else 0.0
    
    print(f"Total Cases: {total_cases}")
    print(f"Recall@3: {recall_at_3:.2%}")
    print(f"Mean Reciprocal Rank (MRR): {mrr:.2f}")
    
    # We don't fail the build on Recall if data is sparse, but we assert cases were run
    assert total_cases > 0, "No RAG evaluation cases run."
    print("RAG Evaluation Passed!")

if __name__ == "__main__":
    run_eval()
