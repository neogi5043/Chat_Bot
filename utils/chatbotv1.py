# import pandas as pd
# import json
# from datetime import datetime
# import llm  # Import local llm.py
# import db   # Import local db.py
# from prompt import INSIGHTS_GENERATION_PROMPT
# # --- Main Logic Pipeline ---
# def pipeline(query_request):
#     try:
#         # 1. Classify Intent
#         intent = llm.classify_intent(query_request)
        
#         # 2. Handle based on intent
#         if intent == "general_conversation":
#             # Handle conversational queries without SQL
#             response = llm.handle_general_conversation(query_request)
#             return None, None, response, "general"
        
#         # 3. For SQL queries, proceed with normal flow
#         # Generate SQL
#         sql_query = llm.generate_sql(query_request)

#         # 4. Run SQL
#         df = db.run_query(sql_query)

#         # Handle empty results
#         if df is None or df.empty:
#             df = pd.DataFrame([["No results found"]], columns=["Message"])
#             return sql_query, df, None, "sql"

#         # 5. Generate Insights
#         insights = llm.generate_insights(df, original_query=query_request)

#         return sql_query, df, insights, "sql"
    
#     except Exception as e:
#         err_df = pd.DataFrame([[str(e)]], columns=["Error"])
#         return f"Error: {str(e)}", err_df, None, "error"

# def main():
#     query_request = "hi,what are demands?"
#     sql_query, df, insights, query_type = pipeline(query_request)

#     if query_type == "general":
#         # General conversation response
#         print("Response:")
#         print(insights)
#     elif query_type == "sql":
#         # SQL query response
#         print("Generated SQL:")
#         print(sql_query)
#         print("\n" + "="*50 + "\n")

#         # Convert DataFrame → JSON
#         json_data = df.to_json(orient="records")
#         parsed_json = json.loads(json_data)
        
#         print("Result in JSON:")
#         print(json.dumps(parsed_json, indent=4))
#         print("\n" + "="*50 + "\n")

#         # Display Insights
#         if insights:
#             print("Insights:")
#             print(insights)
#         else:
#             print("No insights generated.")
#     else:
#         # Error response
#         print("Error occurred:")
#         print(sql_query)
#         print(df)

# if __name__ == "__main__":
#     main()