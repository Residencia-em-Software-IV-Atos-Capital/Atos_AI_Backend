from fastapi import APIRouter, Query, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from app.models.request_models import QueryRequest # type:ignore
from app.services.ai_service import generate_ai_response # type:ignore
from app.services.db_service import execute_sql_query, GLOBAL_ASYNC_ENGINE # Importa o engine e a função de execução # type:ignore
from sqlalchemy.ext.asyncio import AsyncSession # Importa o tipo de sessão
import pandas as pd
import io
import os
from dotenv import load_dotenv
import asyncio

# Importações do ReportLab CORRIGIDAS
from reportlab.lib.pagesizes import letter, A4 
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import re # <-- Garanta que 're' (regex) esteja importado

# --- Configuração do Ambiente ---
load_dotenv()
db_connection_string = os.getenv("DATABASE_URL")

if not db_connection_string:
    raise ValueError("A variável de ambiente 'DATABASE_URL' não está definida.")

router = APIRouter()

# --- FUNÇÃO AUXILIAR NECESSÁRIA PARA O PDF ---
def _safe_filename(text: str) -> str:
    """Garante que o nome do arquivo seja seguro."""
    text = text.replace(" ", "_")
    # Usa o módulo 're' para remover caracteres inválidos
    return re.sub(r'[^\w\-_\.]', '', text)[:50] 
# -----------------------------------------------------------------


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
    """
    Gera um PDF robusto:
    """
    df = pd.DataFrame(data or [])
    buffer = io.BytesIO()

    # Página e margens
    page_size = A4 
    left, right, top, bottom = 24, 24, 36, 36

    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=left,
        rightMargin=right,
        topMargin=top,
        bottomMargin=bottom
    )

    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    normal_style = styles["Normal"]

    elements = []

    # Título
    title_text = title or "Relatório BI"
    elements.append(Paragraph(title_text, title_style))
    elements.append(Spacer(1, 0.25 * inch))

    # Dataset vazio
    if df.empty:
        elements.append(Paragraph("Nenhum dado encontrado para a consulta.", normal_style))
        doc.build(elements)
        buffer.seek(0)
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={_safe_filename(title_text)}.pdf"}
        )

    # Construção dos dados para a tabela (tudo como string)
    headers = [str(c) for c in df.columns.tolist()]
    rows = [
        [("" if pd.isna(v) else str(v)) for v in row]
        for row in df.itertuples(index=False, name=None)
    ]
    table_data = [headers] + rows

    # Cálculo de larguras de coluna para caber na página
    available_width = page_size[0] - left - right
    font_size_body = 8
    avg_char_width = font_size_body * 0.55
    
    max_chars_per_col = []
    sample_rows = rows[:1000]
    for j in range(len(headers)):
        max_len = len(headers[j])
        for r in sample_rows:
            if j < len(r):
                l = len(r[j] or "")
                if l > max_len:
                    max_len = l
        max_chars_per_col.append(min(max_len, 40))

    raw_widths = [max(50, m * avg_char_width + 12) for m in max_chars_per_col]
    scale = min(1.0, available_width / sum(raw_widths))
    col_widths = [w * scale for w in raw_widths]

    table = Table(table_data, colWidths=col_widths, repeatRows=1, splitByRow=1)

    table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), font_size_body),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f7f7f7")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
    table.setStyle(table_style)

    elements.append(table)

    # Constrói o PDF
    try:
        doc.build(elements)
    except Exception as e:
        # Fallback: se der erro de layout, gera um PDF com mensagem
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=page_size,
            leftMargin=left,
            rightMargin=right,
            topMargin=top,
            bottomMargin=bottom
        )
        elements = [
            Paragraph(title_text, title_style),
            Spacer(1, 0.25 * inch),
            Paragraph(f"Falha ao renderizar a tabela: {str(e)}", normal_style)
        ]
        doc.build(elements)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={_safe_filename(title_text)}.pdf"}
    )

def generate_xlsx_response(data: list, title: str) -> StreamingResponse:
    """
    Gera um XLSX com largura de coluna ajustada e cabeçalho congelado.
    """
    df = pd.DataFrame(data or [])
    buffer = io.BytesIO()

    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        wdf = df if not df.empty else pd.DataFrame({"Mensagem": ["Nenhum dado encontrado para a consulta."]})
        wdf.to_excel(writer, index=False, sheet_name="Report", freeze_panes=(1, 0))
        ws = writer.sheets["Report"]

        # Ajusta largura das colunas
        for col_idx, column in enumerate(wdf.columns, start=1):
            col_values = wdf[column].astype(str)
            max_len = max(col_values.map(len).max() if not wdf.empty else 0, len(str(column)))
            ws.column_dimensions[ws.cell(1, col_idx).column_letter].width = min(max_len + 2, 50)

    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={_safe_filename(title)}.xlsx"}
    )

# -----------------------------------------------------------------
# --- NOVAS FUNÇÕES AUXILIARES PARA GERAÇÃO DE DADOS DE DASHBOARD ---
# -----------------------------------------------------------------

async def _generate_kpi_data(user_question: str, db: AsyncSession) -> dict:
    """Gera dados de KPI a partir da pergunta do usuário."""
    # Usando a variável de ambiente como o 'schema' de contexto, como na rota /analyze
    db_schema = db_connection_string 
    
    # PROMPT APRIMORADO: Instruindo a IA a retornar UM ÚNICO VALOR agregado.
    kpi_prompt = f"{user_question}. Gere a query SQL que resulte em UM ÚNICO VALOR (SUM, AVG, COUNT, MAX, MIN) relevante para este KPI. Seu retorno de mensagem deve resumir este valor. Formato: KPI."
    ai_response = await asyncio.to_thread(generate_ai_response, kpi_prompt, db_schema)

    if not ai_response.sql_query:
        return {
            "type": "kpi",
            "status": "error",
            "message": "Não foi possível gerar a consulta SQL para KPI.",
        }

    # Executa a consulta SQL
    data = await execute_sql_query(db, ai_response.sql_query)

    # Lógica de extração de valor para KPI
    value = None
    if data and len(data) > 0:
        first_row = data[0]
        first_value = list(first_row.values())[0] if isinstance(first_row, dict) else None
        value = first_value

    return {
        "type": "kpi",
        "status": "success",
        "message": ai_response.message or "Indicador gerado com sucesso.",
        "query": ai_response.sql_query,
        "value": value,
        "data": data
    }


async def _generate_bar_data(user_question: str, db: AsyncSession) -> dict:
    """Gera dados para Gráfico de Barras."""
    db_schema = db_connection_string

    # PROMPT APRIMORADO: Instruindo a IA a gerar dados agrupados, especificando eixos.
    bar_prompt = f"{user_question}. Gere a query SQL para um gráfico de barras. A query deve retornar duas colunas: a primeira como EIXO X (categorias) e a segunda como EIXO Y (valores). Formato: BAR."
    ai_response = await asyncio.to_thread(generate_ai_response, bar_prompt, db_schema)

    if not ai_response.sql_query:
        return {
            "type": "bar",
            "status": "error",
            "message": "Não foi possível gerar a consulta SQL para gráfico de barras.",
        }

    data = await execute_sql_query(db, ai_response.sql_query)

    return {
        "type": "bar",
        "status": "success",
        "message": ai_response.message or "Gráfico de barras gerado com sucesso.",
        "query": ai_response.sql_query,
        "data": data,
        "x_axis": ai_response.x_axis,
        "y_axis": ai_response.y_axis,
        "label": ai_response.label,
        "value": ai_response.value
    }


async def _generate_pie_data(user_question: str, db: AsyncSession) -> dict:
    """Gera dados para Gráfico de Pizza."""
    db_schema = db_connection_string

    # PROMPT APRIMORADO: Instruindo a IA a gerar dados para fatias (label e valor).
    pie_prompt = f"{user_question}. Gere a query SQL para um gráfico de pizza. A query deve retornar duas colunas: a primeira para o rótulo (LABEL) e a segunda para o valor correspondente (VALUE). Formato: PIE."
    ai_response = await asyncio.to_thread(generate_ai_response, pie_prompt, db_schema)

    if not ai_response.sql_query:
        return {
            "type": "pie",
            "status": "error",
            "message": "Não foi possível gerar a consulta SQL para gráfico de pizza.",
        }

    data = await execute_sql_query(db, ai_response.sql_query)

    return {
        "type": "pie",
        "status": "success",
        "message": ai_response.message or "Gráfico de pizza gerado com sucesso.",
        "query": ai_response.sql_query,
        "data": data,
        "label": ai_response.label,
        "value": ai_response.value
    }

# -----------------------------------------------------------------
# --- NOVA ROTA CONSOLIDADA PARA DASHBOARD ---
# -----------------------------------------------------------------

@router.post("/dashboard")
async def generate_dashboard(body: QueryRequest, db: AsyncSession = Depends(get_db)):
    """
    Gera dados para um dashboard completo (KPI, Barras e Pizza) a partir de uma única pergunta.
    """
    user_question = body.user_question

    # 1. Cria uma lista de tarefas assíncronas para gerar cada componente
    tasks = [
        _generate_kpi_data(user_question, db),
        _generate_bar_data(user_question, db),
        _generate_pie_data(user_question, db),
    ]

    # 2. Executa todas as tarefas concorrentemente
    results = await asyncio.gather(*tasks)

    # 3. Retorna o resultado final bem estruturado
    return {
        "user_query": user_question,
        "dashboard_components": {
            "kpi": results[0],
            "bar_chart": results[1],
            "pie_chart": results[2],
        },
        "message": "Dashboard components generated successfully."
    }
# -----------------------------------------------------------------
# --- ROTAS DA API ORIGINAIS (MANTIDAS INTACTAS) ---
# -----------------------------------------------------------------


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

        # Lógica de relatórios (CSV, PDF, XLSX) é mantida
        if ai_response.report_type == "csv":
            return await asyncio.to_thread(generate_csv_response, data)
        
        elif ai_response.report_type == "pdf":
            return await asyncio.to_thread(generate_pdf_response, data, report_title)
        
        elif ai_response.report_type == "xlsx":
            return await asyncio.to_thread(generate_xlsx_response, data, report_title)
        
        # AQUI FOI FEITA UMA PEQUENA CORREÇÃO LÓGICA: 
        # as chamadas para kpi, bar e pie dentro do /analyze 
        # não devem retornar arquivos de streaming, mas sim o JSON do analyze.
        # Como as rotas /kpi, /bar e /pie originais foram removidas, 
        # a checagem é simplificada ou mantida apenas para tipos de arquivo.
        # Para evitar problemas, vou manter apenas as checagens de arquivo (csv, pdf, xlsx) 
        # e retornar JSON para o resto, já que o foco é /dashboard.
        
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