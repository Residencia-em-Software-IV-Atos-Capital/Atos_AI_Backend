# Seu arquivo de rotas (ex: app/routes/analysis.py)
# As linhas com "# MUDANÇA" indicam as alterações.

import os
import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, Query, Depends  # MUDANÇA: Importar Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession # MUDANÇA: Importar AsyncSession
import io

from app.models.request_models import QueryRequest
from app.services.ai_service import generate_ai_response
# MUDANÇA: Importar as novas funções do db_service
from app.services.db_service import execute_sql_query, get_db

load_dotenv()
db_connection_string = os.getenv("DATABASE_URL")
if not db_connection_string:
    raise ValueError("A variável de ambiente 'DATABASE_URL' não está definida.")

router = APIRouter()


@router.post("/analyze")
# MUDANÇA: Adicionar a dependência do banco de dados na assinatura da função
async def analyze_data(body: QueryRequest, db: AsyncSession = Depends(get_db)):
    db_schema = db_connection_string
    user_question = body.user_question
    ai_response = await generate_ai_response(user_question, db_schema)

    if ai_response.sql_query:
        if ai_response.visualization_type == "report":
            # A lógica para redirecionar para o relatório continua a mesma
            return {
                "message": ai_response.message,
                "query": ai_response.sql_query,
                "data": None,
                "visualization_type": "report",
                "report_type": ai_response.report_type,
                "redirect_to": f"/report/{ai_response.report_type}?user_question={user_question}" 
            }
        
        # MUDANÇA: Chamar a função com "await" e passar a sessão "db"
        data = await execute_sql_query(db, ai_response.sql_query)
        
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
    else:
        # A lógica para respostas sem query continua a mesma
        return {
            "message": ai_response.message,
            "query": None,
            "data": None,
            "visualization_type": "text",
            "x_axis": None,
            "y_axis": None,
            "label": None,
            "value": None,
        }


@router.get("/report/csv")
# MUDANÇA: Adicionar a dependência do banco aqui também
async def get_csv_report(user_question: str = Query(...), db: AsyncSession = Depends(get_db)):
    ai_response = generate_ai_response(user_question, db_connection_string)
    
    # MUDANÇA: Chamar a função com "await" e passar a sessão "db"
    data = await execute_sql_query(db, ai_response.sql_query)
    
    df = pd.DataFrame(data)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    
    return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment;filename=report.csv"})

# # NOVA ROTA: Geração de Relatórios em PDF
# @router.get("/report/pdf")
# async def get_pdf_report(user_question: str = Query(...)):
#     # Obter a resposta da IA e os dados do banco de dados
#     ai_response = generate_ai_response(user_question, db_connection_string)
#     data = execute_sql_query(db_connection_string, ai_response.sql_query)
    
#     # Criar um DataFrame com os dados
#     df = pd.DataFrame(data)

#     # Preparar o buffer de memória para o PDF
#     buffer = io.BytesIO()
#     doc = SimpleDocTemplate(buffer, pagesize=letter)
#     elements = []
#     styles = getSampleStyleSheet()

#     # Adicionar um título ao documento
#     title_style = ParagraphStyle(
#         name='TitleStyle',
#         parent=styles['Heading1'],
#         alignment=1, # Centralizado
#         spaceAfter=12
#     )
#     elements.append(Paragraph("Relatório de Dados", title_style))
#     elements.append(Paragraph(ai_response.message, styles['Normal']))

#     # Preparar os dados para a tabela do ReportLab
#     # O ReportLab espera uma lista de listas, onde a primeira lista são os cabeçalhos
#     if not df.empty:
#         table_data = [list(df.columns)] + df.values.tolist()
        
#         # Estilo para a tabela
#         table_style = TableStyle([
#             ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
#             ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
#             ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
#             ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
#             ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
#             ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
#             ('GRID', (0, 0), (-1, -1), 1, colors.black),
#         ])

#         # Criar a tabela
#         table = Table(table_data)
#         table.setStyle(table_style)
#         elements.append(table)
#     else:
#         elements.append(Paragraph("Nenhum dado encontrado para o relatório.", styles['Normal']))
        
#     # Construir o PDF
#     doc.build(elements)
    
#     # Voltar para o início do buffer para a resposta
#     buffer.seek(0)
    
#     return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": "attachment;filename=report.pdf"})
