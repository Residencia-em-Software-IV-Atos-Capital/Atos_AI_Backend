from fastapi import APIRouter, Query, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from app.models.request_models import QueryRequest
from app.services.ai_service import generate_ai_response
from app.services.db_service import execute_sql_query, GLOBAL_ASYNC_ENGINE # Importa o engine e a função de execução
from sqlalchemy.ext.asyncio import AsyncSession # Importa o tipo de sessão
import pandas as pd
import io
import os
from dotenv import load_dotenv
import asyncio # <--- GARANTINDO QUE ESTEJA IMPORTADO

# Importações do ReportLab
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

# --- Configuração do Ambiente ---
load_dotenv()
db_connection_string = os.getenv("DATABASE_URL")

if not db_connection_string:
    raise ValueError("A variável de ambiente 'DATABASE_URL' não está definida.")

router = APIRouter()

# --- Dependência para Injeção de Sessão Assíncrona ---
async def get_db():
    if GLOBAL_ASYNC_ENGINE is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="O motor assíncrono do banco de dados não foi inicializado."
        )
    # Abre uma nova conexão assíncrona para cada requisição
    async with GLOBAL_ASYNC_ENGINE.begin() as connection:
        yield connection


# --- Funções Auxiliares (Geração de Arquivo) ---

def generate_csv_response(data: list) -> StreamingResponse:
    """Converte a lista de dicionários em um arquivo CSV e retorna um StreamingResponse."""
    df = pd.DataFrame(data)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer, 
        media_type="text/csv", 
        headers={"Content-Disposition": "attachment;filename=report.csv"}
    )

def generate_pdf_response(data: list, title: str) -> StreamingResponse:
    """Gera um relatório PDF com uma tabela a partir dos dados (SÍNCRONO)."""
    df = pd.DataFrame(data)
    table_data = [df.columns.tolist()] + df.values.tolist()
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    elements.append(Paragraph(f"Relatório BI: {title}", styles['h1']))
    elements.append(Spacer(1, 0.5 * inch))

    table = Table(table_data)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    doc.build(elements)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment;filename={title.replace(' ', '_').lower()}.pdf"}
    )


# --- Rotas da API ---

@router.post("/analyze")
async def analyze_data(body: QueryRequest, db: AsyncSession = Depends(get_db)): 
    user_question = body.user_question
    db_schema = db_connection_string 
    
    # 2. Gere a resposta da IA (Bloqueante/Síncrona)
    # CORREÇÃO APLICADA: Chama a função síncrona de forma segura
    ai_response = await asyncio.to_thread(generate_ai_response, user_question, db_schema)
    
    # 3. Se não há query, retorna erro ou mensagem de texto
    if not ai_response.sql_query:
        return {
            "message": ai_response.message,
            "query": None,
            "data": None,
            "visualization_type": "text", 
            "x_axis": None, "y_axis": None, "label": None, "value": None,
        }
        
    # 4. Executa a query SQL AGORA ASSÍNCRONA
    # NOTA: execute_sql_query DEVE ser async def e receber 'db' como parâmetro,
    # caso contrário, esta linha também causaria um erro.
    data = await execute_sql_query(db, ai_response.sql_query) 
    
    # 5. Verifica se é um relatório e retorna o arquivo apropriado
    if ai_response.visualization_type == "report":
        
        report_title = ai_response.message if ai_response.message else user_question

        if ai_response.report_type == "csv":
            # Retorna o arquivo CSV (Síncrono - usa asyncio.to_thread)
            return await asyncio.to_thread(generate_csv_response, data)
        
        elif ai_response.report_type == "pdf":
            # Retorna o arquivo PDF (Síncrono - usa asyncio.to_thread)
            return await asyncio.to_thread(generate_pdf_response, data, report_title)
        
        # Se a IA pediu um relatório, mas o formato não é reconhecido, retorna JSON com os dados
        return {
            "message": f"Formato de relatório '{ai_response.report_type}' não suportado. Dados brutos retornados.",
            "query": ai_response.sql_query,
            "data": data,
            "visualization_type": "table",
            "x_axis": None, "y_axis": None, "label": None, "value": None,
        }
        
    # 6. Se não for relatório (gráfico/tabela), retorna o JSON para o front-end
    return {
        "message": ai_response.message,
        "query": ai_response.sql_query,
        "data": data,
        "visualization_type": ai_response.visualization_type,
        "x_axis": ai_response.x_axis,
        "y_axis": ai_response.y_axis,
        "label": ai_response.label,
        "value": ai_response.value,
    }
