from typing import Any
import time

class ExecutionResult:
    def __init__(self, success: bool, data: Any = None, error: str = None, execution_time_ms: float = 0):
        self.success = success
        self.data = data
        self.error = error
        self.execution_time_ms = execution_time_ms

from src.common.db import release_connection

class ExecutionEngine:
    """
    Safely executes SQL and handles errors.
    """
    
    def __init__(self, database_connection_factory):
        self.get_db_connection = database_connection_factory
    
    def execute(self, sql: str) -> ExecutionResult:
        conn = None
        start_time = time.time()
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute(sql)
            
            # Fetch results
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                data = [dict(zip(columns, row)) for row in rows]
            else:
                data = [] # e.g. for UPDATE/INSERT, but we mostly do SELECT
                
            cursor.close()
            
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(success=True, data=data, execution_time_ms=duration)

        except Exception as e:
            duration = (time.time() - start_time) * 1000
            return ExecutionResult(success=False, error=str(e), execution_time_ms=duration)
        finally:
            if conn:
                release_connection(conn)
