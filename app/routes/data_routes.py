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

@router.post("/analyze")
async def analyze_data(body: QueryRequest):
    # 1. Obtenha a string de conexão e a pergunta do usuário
    db_schema = db_connection_string  # Substitua pela sua variável/configuração
    user_question = body.user_question

    # 2. Gere a resposta da IA (esta parte já está funcionando bem)
    ai_response = generate_ai_response(user_question, db_schema)

    # 3. VERIFICAÇÃO CRÍTICA: Existe uma consulta para executar?
    # Esta é a lógica que resolve o seu problema.
    if ai_response.sql_query:
        
        # 3a. SIM, existe uma query. Agora decidimos como processá-la.
        
        # É um relatório para exportar?
        if ai_response.visualization_type == "report":
            return {
                "message": ai_response.message,
                "query": ai_response.sql_query,
                "data": None,
                "visualization_type": "report",
                "report_type": ai_response.report_type,
                # O frontend pode usar este campo para chamar a rota de download correta
                "redirect_to": f"/report/{ai_response.report_type}?user_question={user_question}" 
            }
        
        # Não é um relatório, então é um gráfico/tabela. EXECUTAMOS A QUERY.
        data = execute_sql_query(db_schema, ai_response.sql_query)
        
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
        # 3b. NÃO, não existe uma query (sql_query é None).
        # Este é o nosso fluxo de conversa.
        # Nós NÃO chamamos execute_sql_query. Apenas retornamos a mensagem.
        return {
            "message": ai_response.message,
            "query": ai_response.sql_query, # Será None
            "data": None,
            "visualization_type": "text", # Informa ao frontend que é só texto
            "x_axis": None,
            "y_axis": None,
            "label": None,
            "value": None,
        }

# A rota /report/csv permanece a mesma, mas agora você pode ter rotas separadas
# para PDF e XLSX que processam o mesmo fluxo
@router.get("/report/csv")
async def get_csv_report(user_question: str = Query(...)):
    ai_response = generate_ai_response(user_question, db_connection_string)
    
    data = execute_sql_query(db_connection_string, ai_response.sql_query)
    
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
