
import sys
import os

# Add src to python path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from agents.feedback_manager import FeedbackManager

def debug_fm():
    print("Initializing FeedbackManager...")
    fm = FeedbackManager()
    
    query = "What is the average fulfillment time for Cloud and devops"
    print(f"\nQuery: {query}")
    
    # This calls the method I added debug prints to
    correct, incorrect = fm.get_similar_feedback(query)
    
    print(f"\nResult Correct: {len(correct)}")
    for c in correct:
        print(f" - ID: {c.get('id')} | Q: {c.get('user_question')}")

if __name__ == "__main__":
    debug_fm()
