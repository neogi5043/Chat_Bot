import json
import time
from chatbot import pipeline
from db import get_connection
import psycopg2
from psycopg2.extras import RealDictCursor

GOLD_TEST_FILE = "training_data/gold_tests.json"

class BenchmarkEvaluator:
    def __init__(self, gold_test_file):
        with open(gold_test_file, 'r') as f:
            self.gold_tests = json.load(f)
    
    def normalize_sql(self, sql):
        # Basic normalization to compare SQLs (rendering distinct from spaces/caps)
        if not sql: return ""
        return " ".join(sql.lower().split())

    def run_benchmark(self):
        print(f"Starting Benchmark on {len(self.gold_tests)} tests...")
        results = []
        
        for test in self.gold_tests:
            print(f"Running Test {test['id']}: {test['user_question']}")
            
            start_time = time.time()
            try:
                # We use the existing pipeline. 
                # Note: The pipeline returns a result object or string. 
                # We need to capture the GENERATED SQL from it. 
                # Currently chatbot.pipeline returns distinct things depending on mode.
                # For this benchmark, we might need to modify chatbot.py to expose the SQL 
                # or rely on logs/metadata if available.
                
                # HACK: For now, we assume pipeline returns a response where we can't easily extract SQL
                # without modifying the code. So we will evaluate based on DATA MATCH (if we can)
                # or just Execution Success for now.
                
                # Ideally, we should import the `generate_sql` function directly from llm.py 
                # to test the SQL generation part specifically.
                
                from llm import generate_sql
                generated_sql = generate_sql(test['user_question'])
                
                execution_time = (time.time() - start_time) * 1000
                
                # 1. Execution Success
                cursor = get_connection()
                exec_success = False
                try:
                    cur = cursor.cursor()
                    cur.execute(generated_sql)
                    cur.close()
                    exec_success = True
                except Exception as e:
                    print(f"  Execution Failed: {e}")
                finally:
                    cursor.close()

                # 2. Exact Match (Naive)
                exact_match = self.normalize_sql(generated_sql) == self.normalize_sql(test['gold_sql'])
                
                results.append({
                    "id": test['id'],
                    "success": exec_success,
                    "exact_match": exact_match,
                    "time_ms": execution_time,
                    "generated_sql": generated_sql
                })
                
                print(f"  Result: Success={exec_success}, Time={execution_time:.2f}ms")

            except Exception as e:
                print(f"  System Error: {e}")
                results.append({"id": test['id'], "success": False, "error": str(e)})

        # Summary
        success_rate = sum(1 for r in results if r.get('success')) / len(results) * 100
        print("\n" + "="*30)
        print(f"BENCHMARK COMPLETE")
        print(f"Execution Success Rate: {success_rate:.1f}%")
        print("="*30)

if __name__ == "__main__":
    evaluator = BenchmarkEvaluator(GOLD_TEST_FILE)
    evaluator.run_benchmark()
