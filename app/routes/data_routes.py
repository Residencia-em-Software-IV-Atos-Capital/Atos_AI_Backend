from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.models.request_models import QueryRequest
from app.services.ai_service import generate_ai_response
from app.services.db_service import execute_sql_query
import pandas as pd
import io
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import os

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Obtém a string de conexão da variável de ambiente
db_connection_string = os.getenv("DATABASE_URL")

# Verifica se a string de conexão foi carregada
if not db_connection_string:
    raise ValueError("A variável de ambiente 'DATABASE_URL' não está definida.")

router = APIRouter()

@router.post("/analyze")
async def analyze_data(body: QueryRequest, request: Request):
    db_schema = request.app.state.db_schema
    ai_response = generate_ai_response(body.user_question, db_schema)
    
    data = execute_sql_query(ai_response.sql_query)
    
    return {
        "data": data,
        "visualization_type": ai_response.visualization_type,
        "x_axis": ai_response.x_axis,
        "y_axis": ai_response.y_axis,
        "label": ai_response.label,
        "value": ai_response.value,
    }


@router.post("/report/csv")
async def get_csv_report(body: QueryRequest, request: Request):

    db_schema = request.app.state.db_schema
    ai_response = generate_ai_response(body.user_question, db_schema)
    
    data = execute_sql_query(ai_response.sql_query)

    df = pd.DataFrame(data)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    
    return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment;filename=report.csv"})

@router.post("/report/kpi")
async def get_kpi_report(body: QueryRequest, request: Request):
    """
    Gera um valor de KPI (Key Performance Indicator)
    a partir de uma pergunta do usuário.
    """
    db_schema = request.app.state.db_schema
    ai_response = generate_ai_response(body.user_question, db_schema)

    data = execute_sql_query(ai_response.sql_query)
    
    if not data or not data[0]:
        raise HTTPException(status_code=404, detail="No data found for the KPI.")

    # Retorna o primeiro valor da primeira linha como KPI
    kpi_value = list(data[0].values())[0]

    return {
        "kpi_value": kpi_value,
        "label": ai_response.label,
    }


@router.post("/report/bar")
async def get_bar_chart_data(body: QueryRequest, request: Request):
    """
    Gera dados para um gráfico de barras a partir de uma pergunta do usuário.
    """
    db_schema = request.app.state.db_schema
    ai_response = generate_ai_response(body.user_question, db_schema)

    data = execute_sql_query(ai_response.sql_query)
    
    return {
        "data": data,
        "x_axis": ai_response.x_axis,
        "y_axis": ai_response.y_axis,
    }


@router.post("/report/pie")
async def get_pie_chart_data(body: QueryRequest, request: Request):
    """
    Gera dados para um gráfico de pizza a partir de uma pergunta do usuário.
    """
    db_schema = request.app.state.db_schema
    ai_response = generate_ai_response(body.user_question, db_schema)
    
    data = execute_sql_query(ai_response.sql_query)
    
    return {
        "data": data,
        "label": ai_response.label,
        "value": ai_response.value
    }