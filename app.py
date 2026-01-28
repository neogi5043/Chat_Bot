import time
import pandas as pd
import chatbot
import llm

def print_user(msg):
    print(f"\n👤 You: {msg}")

def print_bot(msg):
    print(f"\n🤖 Bot: {msg}")

def print_system(msg):
    print(f"   [System]: {msg}")

def main():
    print("="*60)
    print("      DEMAND MANAGEMENT CRM BOT (Interactive Mode)")
    print("="*60)
    print_bot("Hello! I can help you with Demands, Candidates, and Reports.")
    print_bot("Ask me anything (or type 'exit' to quit).")

    while True:
        try:
            user_input = input("\n👉 Enter your query: ").strip()
            
            if user_input.lower() in ['exit', 'quit', 'bye']:
                print_bot("Goodbye! 👋")
                break
                
            if not user_input:
                continue

            # Show "Thinking..." state
            print_system("Thinking...")
            start_time = time.time()
            
            # Run pipeline (Hidden from user)
            # pipeline returns: sql_query, df, insights, intent
            sql_query, df, insights, intent = chatbot.pipeline(user_input, verbose=False)
            
            # Handle Based on Intent
            if intent == "general_conversation":
                print_bot(insights)
                continue
                
            elif intent == "error":
                print_bot("I encountered an issue processing your request.")
                if df is not None and not df.empty:
                     print_system(f"Error details: {df.iloc[0,0]}")
                
                # Auto-log failure
                # (Already handled inside pipeline, but we can ask for more details if needed)
                continue

            # Success Case
            print_bot(insights)
            
            if df is not None and not df.empty and intent == "sql":
                # Check if the result is just a message (e.g. empty result feedback)
                if len(df.columns) == 1 and df.columns[0] == "Message":
                    print("\n" + df.iloc[0,0])
                else:
                    # Show data neatly
                    print("\n📊 Data Overview:")
                    print("-" * 40)
                    if len(df) > 10:
                        print(df.head(10).to_string(index=False))
                        print(f"... and {len(df)-10} more rows.")
                    else:
                        print(df.to_string(index=False))
                    print("-" * 40)

            # HITL FEEDBACK STEP
            print("\n" + "."*40)
            feedback = input("   👍 Is this answer helpful? (y/n): ").strip().lower()
            
            if feedback == 'y':
                # Reward
                llm.feedback_manager.log_feedback(user_input, sql_query, True)
                print_system("Thanks! I'll remember this for next time.")
                
            elif feedback == 'n':
                # Penalty
                reason = input("   Sorry about that. What was wrong? (optional): ").strip()
                error_msg = f"User rejected result. Reason: {reason}" if reason else "User rejected result"
                
                llm.feedback_manager.log_feedback(user_input, sql_query, False, error_msg)
                print_system("Feedback received. I'll avoid this mistake in the future.")
        
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print_system(f"Critical Error: {e}")

if __name__ == "__main__":
    main()
