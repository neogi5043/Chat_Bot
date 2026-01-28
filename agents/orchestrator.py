from .semantic_layer import SemanticLayer
from .schema_selector import SchemaSelectorAgent
from .entity_resolver import EntityResolverAgent
from .decomposer import DecomposerAgent
from .sql_generator import SQLGeneratorAgent
from .validator import ValidatorAgent
from .execution_engine import ExecutionEngine
from .correction_agent import CorrectionAgent
from .feedback_manager import FeedbackManager
from db import get_connection

class TextToSQLOrchestrator:
    """
    Orchestrates the complete pipeline from natural language to results.
    """
    
    def __init__(self):
        # Initialize all agents
        self.semantic_layer = SemanticLayer()
        self.feedback_manager = FeedbackManager()
        self.schema_selector = SchemaSelectorAgent(self.semantic_layer)
        self.entity_resolver = EntityResolverAgent(self.semantic_layer)
        self.decomposer = DecomposerAgent()
        # Pass feedback manager to SQL generator for few-shot learning
        self.sql_generator = SQLGeneratorAgent(self.semantic_layer, self.feedback_manager)
        self.validator = ValidatorAgent(get_connection)
        self.executor = ExecutionEngine(get_connection)
        self.corrector = CorrectionAgent(self.sql_generator)
        
    def process_query(self, user_query: str, user_email: str = None) -> dict:
        """
        Complete end-to-end pipeline.
        """
        print(f"Processing query: {user_query}")
        
        # Phase 1: Schema Selection
        selected_schema = self.schema_selector.select_schema(user_query)
        print(f"Selected {len(selected_schema)} tables")
        
        # Phase 2: Entity Resolution
        entity_resolutions = self.entity_resolver.resolve_entities(
            user_query, 
            selected_schema
        )
        print(f"Resolved {len(entity_resolutions)} entities: {entity_resolutions}")
        
        # Phase 3: Query Decomposition
        query_plan = self.decomposer.decompose(user_query, self.semantic_layer)
        
        # Phase 4: SQL Generation
        generated_sql = self.sql_generator.generate_sql(
            query_plan=query_plan,
            selected_schema=selected_schema,
            entity_resolutions=entity_resolutions,
            user_query=user_query
        )
        print(f"Generated SQL: {generated_sql}")
        
        # Phase 5: Validation
        validation = self.validator.validate(generated_sql, selected_schema)
        
        final_sql = generated_sql
        
        # Try to fix if invalid
        if not validation.is_valid:
             print(f"Validation Errors: {validation.errors}. Attempting fix...")
             fix_result = self.corrector.attempt_correction(
                 generated_sql, 
                 str(validation.errors), 
                 user_query,
                 "Schema in prompt" # simplified
             )
             if fix_result["success"]:
                 final_sql = fix_result["corrected_sql"]
                 print(f"Corrected SQL: {final_sql}")
             else:
                 return {
                    "success": False,
                    "error": "SQL validation failed and auto-correction failed",
                    "sql": generated_sql
                }
        
        # Phase 6: Execution
        exec_result = self.executor.execute(final_sql)
        print(f"Execution success: {exec_result.success}")
        
        # Phase 7: Error Handling & Correction (Runtime Errors)
        if not exec_result.success:
            print("Runtime error. Attempting fix...")
            fix_result = self.corrector.attempt_correction(
                 final_sql, 
                 exec_result.error, 
                 user_query,
                 "Schema in prompt"
             )
            
            if fix_result["success"]:
                # Retry execution
                final_sql = fix_result["corrected_sql"]
                exec_result = self.executor.execute(final_sql)
                print(f"Retry success: {exec_result.success}")
            
        # Log Feedback (Auto-log failure if final attempt failed)
        if not exec_result.success:
            self.feedback_manager.log_feedback(
                query=user_query,
                sql=final_sql,
                success=False,
                error_msg=exec_result.error
            )
        else:
             # We log success implicitly, or let user do it explicitly via app.py
             # For now, let's auto-log success if verification passed to populate history
             pass

        return {
            "success": exec_result.success,
            "data": exec_result.data,
            "error": exec_result.error,
            "sql": final_sql,
            "metadata": {
                "tables_used": [t.get('table_id') for t in selected_schema], # safe get
                "query_plan_steps": len(query_plan.get('steps', []))
            }
        }
