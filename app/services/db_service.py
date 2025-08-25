from sqlalchemy import inspect, text
from app.core.db_connector import engine
from fastapi import HTTPException

def get_database_schema(schema: str = "unit") -> str:
    try:
        inspector = inspect(engine)
        table_names = inspector.get_table_names(schema=schema)
        schema_string = ""
        for table_name in table_names:
            schema_string += f"Tabela `{schema}.{table_name}`:\n"
            columns = inspector.get_columns(table_name, schema=schema)
            for column in columns:
                column_type = str(column['type']).upper()
                schema_string += f"- `{column['name']}` ({column_type})\n"
            schema_string += "\n"
        return schema_string
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor: {e}")


def execute_sql_query(sql_query: str) -> list:
    try:
        with engine.connect() as connection:
            result = connection.execute(text(sql_query))
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno do servidor: {e}")