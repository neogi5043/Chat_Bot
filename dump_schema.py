from db import fetch_schema
import json

def dump_schema():
    schema = fetch_schema()
    with open('schema_full.json', 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2)
    print("Schema dumped to schema_full.json")

if __name__ == "__main__":
    dump_schema()
