from db import run_query

def list_practices():
    df = run_query("SELECT practice_id, practice_name FROM practices")
    print(df.to_string())

if __name__ == "__main__":
    list_practices()
