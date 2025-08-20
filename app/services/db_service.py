from sqlalchemy import create_engine, inspect, text
from fastapi import HTTPException

def get_database_schema(db_url: str) -> str:
    """Extrai e formata o esquema do banco de dados usando SQLAlchemy."""
    try:
        engine = create_engine(db_url)
        inspector = inspect(engine)
        table_names = inspector.get_table_names()
        schema_string = ""
        for table_name in table_names:
            schema_string += f"Tabela `{table_name}`:\n"
            columns = inspector.get_columns(table_name)
            for column in columns:
                column_type = str(column['type']).upper()
                schema_string += f"- `{column['name']}` ({column_type})\n"
            schema_string += "\n"
        return schema_string
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro de conexão ou ao extrair o esquema: {e}")

def execute_sql_query(db_url: str, sql_query: str) -> list:
    """Executa a consulta SQL e retorna os dados como uma lista de dicionários."""
    try:
        engine = create_engine(db_url)
        with engine.connect() as connection:
            result = connection.execute(text(sql_query))
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao executar a consulta SQL: {e}")