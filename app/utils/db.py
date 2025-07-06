from app import db
from sqlalchemy import text

class Database:
    @staticmethod
    def fetch_all(query: str, params: dict = None):
        """Execute a query and return all results"""
        try:
            result = db.session.execute(text(query), params or {})
            return result.mappings().all()
        except Exception as e:
            db.session.rollback()
            print(f"Database error in fetch_all: {str(e)}")
            print(f"Error type: {type(e)}")
            print(f"Error args: {e.args}")
            raise
        finally:
            db.session.close()

    @staticmethod
    def execute(query: str, params: dict = None):
        """Execute a command (insert, update, delete)"""
        try:
            result = db.session.execute(text(query), params or {})
            db.session.commit()
            return result
        except Exception as e:
            db.session.rollback()
            print(f"Database error in execute: {str(e)}")
            print(f"Error type: {type(e)}")
            print(f"Error args: {e.args}")
            raise
        finally:
            db.session.close()

    @staticmethod
    def call_procedure(proc_name: str, params: dict = None):
        """Execute a stored procedure and fetch raw results."""
        try:
            query = f"CALL {proc_name}()" if not params else f"CALL {proc_name}({', '.join([f':{key}' for key in params.keys()])})"
            print(f"Executing query: {query} with params: {params}")

            result = db.session.execute(text(query), params or {}).fetchall()
            db.session.commit()  # Added commit here
            print(f"Raw result: {result}")

            return result

        except Exception as e:
            db.session.rollback()
            print(f"Database error in procedure {proc_name}: {str(e)}")
            print(f"Error type: {type(e)}")
            print(f"Error args: {e.args}")
            raise
        finally:
            db.session.close()