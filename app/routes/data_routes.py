import os
from dotenv import load_dotenv
from fastapi import APIRouter
from app.models.request_models import QueryRequest
from app.services.ai_service import generate_ai_response
from app.services.db_service import get_database_schema, execute_sql_query
import pandas as pd
import io
from fastapi.responses import StreamingResponse

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Obtém a string de conexão da variável de ambiente
db_connection_string = os.getenv("DATABASE_URL")

# Verifica se a string de conexão foi carregada
if not db_connection_string:
    raise ValueError("A variável de ambiente 'DATABASE_URL' não está definida.")

router = APIRouter()

@router.post("/analyze")
async def analyze_data(request: QueryRequest):
    """
    Endpoint principal que recebe a pergunta e retorna os dados formatados para visualização.
    """
    db_schema = get_database_schema(db_connection_string)
    ai_response = generate_ai_response(request.user_question, db_schema)
    
    # Executa a consulta SQL usando a string do .env
    data = execute_sql_query(db_connection_string, ai_response.sql_query)
    
    # Retorna a resposta completa com os dados e as informações de visualização
    return {
        "data": data,
        "visualization_type": ai_response.visualization_type,
        "x_axis": ai_response.x_axis,
        "y_axis": ai_response.y_axis,
        "label": ai_response.label,
        "value": ai_response.value,
    }

@router.post("/report/csv")
async def get_csv_report(request: QueryRequest):
    """
    Endpoint para gerar um relatório CSV.
    """
    db_schema = get_database_schema(db_connection_string)
    ai_response = generate_ai_response(request.user_question, db_schema)
    
    # A IA forneceu a query, agora a executamos usando a string do .env
    data = execute_sql_query(db_connection_string, ai_response.sql_query)

    df = pd.DataFrame(data)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    
    return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment;filename=report.csv"})