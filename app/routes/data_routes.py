# app/routes/data_routes.py
# ... (restante das importações e configurações)

import os
import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
import io

from app.models.request_models import QueryRequest
from app.services.ai_service import generate_ai_response
from app.services.db_service import execute_sql_query

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

# Obtém a string de conexão da variável de ambiente
db_connection_string = os.getenv("DATABASE_URL")

# Verifica se a string de conexão foi carregada
if not db_connection_string:
    raise ValueError("A variável de ambiente 'DATABASE_URL' não está definida.")

router = APIRouter()

# A rota principal agora é responsável por direcionar o usuário para a rota correta
# No seu arquivo de rotas (provavelmente routes/analysis.py ou similar)

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
    """
    Gera um relatório PDF com uma tabela a partir dos dados.
    """
    # 1. Preparação dos dados
    df = pd.DataFrame(data)
    # Converte o DataFrame para o formato de lista de listas exigido pelo ReportLab
    table_data = [df.columns.tolist()] + df.values.tolist()
    
    # 2. Criação do buffer de memória
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # 3. Adiciona Título
    elements.append(Paragraph(f"Relatório BI: {title}", styles['h1']))
    elements.append(Spacer(1, 0.5 * inch))

    # 4. Cria a Tabela
    table = Table(table_data)
    
    # Estilo da Tabela
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey), # Cabeçalho cinza
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige), # Linhas alternadas
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    
    # 5. Constrói o PDF no buffer
    doc.build(elements)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment;filename={title.replace(' ', '_').lower()}.pdf"}
    )

@router.post("/analyze")
async def analyze_data(body: QueryRequest):
    # 1. Obtenha a string de conexão e a pergunta do usuário
    user_question = body.user_question
    db_schema = db_connection_string # Usado como esquema de BD
    
    # 2. Gere a resposta da IA (query SQL e tipo de visualização)
    ai_response = generate_ai_response(user_question, db_schema)
    
    # 3. Se não há query, retorna erro ou mensagem de texto
    if not ai_response.sql_query:
        # Lógica para mensagens de texto (ex: "Não entendi a pergunta")
        return {
            "message": ai_response.message,
            "query": None,
            "data": None,
            "visualization_type": "text", 
            "x_axis": None, "y_axis": None, "label": None, "value": None,
        }
        
    # 4. Executa a query SQL
    data = execute_sql_query(db_connection_string, ai_response.sql_query)
    
    # 5. Verifica se é um relatório e retorna o arquivo apropriado
    if ai_response.visualization_type == "report":
        
        # Gera Título para o Relatório (usa a mensagem da IA ou a pergunta)
        report_title = ai_response.message if ai_response.message else user_question

        if ai_response.report_type == "csv":
            # Retorna o arquivo CSV
            return generate_csv_response(data)
        
        elif ai_response.report_type == "pdf":
            # Retorna o arquivo PDF
            return generate_pdf_response(data, report_title)
        
        # Adicione outros formatos de relatório (xlsx) aqui.

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

# A rota /report/csv permanece a mesma, mas agora você pode ter rotas separadas
# para PDF e XLSX que processam o mesmo fluxo
# @router.get("/report/csv")
# async def get_csv_report(user_question: str = Query(...)):
#     ai_response = generate_ai_response(user_question, db_connection_string)
    
#     data = execute_sql_query(db_connection_string, ai_response.sql_query)
    
#     df = pd.DataFrame(data)
#     buffer = io.StringIO()
#     df.to_csv(buffer, index=False)
#     buffer.seek(0)
    
#     return StreamingResponse(buffer, media_type="text/csv", headers={"Content-Disposition": "attachment;filename=report.csv"})


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
