# -*- coding: utf-8 -*-
from fastapi import APIRouter, Query, Depends, HTTPException, status
import asyncio
import google.generativeai as genai
from app.core.config import settings
from fastapi.responses import StreamingResponse
from app.models.request_models import QueryRequest
from app.services.ai_service import generate_ai_response
from app.services.db_service import execute_sql_query, GLOBAL_ASYNC_ENGINE
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy import text
import pandas as pd
import io
import os
from dotenv import load_dotenv
import asyncio

# Importacoes do ReportLab CORRIGIDAS
from reportlab.lib.pagesizes import letter, A4 
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import re

# --- Configuracao do Ambiente ---
load_dotenv()
db_connection_string = os.getenv("DATABASE_URL") or ""

router = APIRouter()

# --- FUNCAO AUXILIAR NECESSARIA PARA O PDF ---
def _safe_filename(text: str) -> str:
    """Garante que o nome do arquivo seja seguro."""
    text = text.replace(" ", "_")
# Usa o modulo 're' para remover caracteres invalidos
    return re.sub(r'[^\w\-_\.]', '', text)[:50] 
# -----------------------------------------------------------------


# --- Dependencia para Injecao de Sessao Assincrona ---
async def get_db():
    if GLOBAL_ASYNC_ENGINE is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="O motor assincrono do banco de dados nao foi inicializado."
        )
    # Abre uma nova conexao assincrona para cada requisicao
    async with GLOBAL_ASYNC_ENGINE.connect() as connection:
        await connection.execute(text("SET search_path TO unit"))
        yield connection


# --- Funcoes Auxiliares (Geracao de Arquivo) ---

def generate_csv_response(data: list) -> StreamingResponse:
    """Converte a lista de dicionarios em um arquivo CSV e retorna um StreamingResponse."""
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

    # Pagina e margens
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

    # Titulo
    title_text = title or "Relatorio BI"
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

    # Construcao dos dados para a tabela (tudo como string)
    headers = [str(c) for c in df.columns.tolist()]
    rows = [
        [("" if pd.isna(v) else str(v)) for v in row]
        for row in df.itertuples(index=False, name=None)
    ]
    table_data = [headers] + rows

    # Calculo de larguras de coluna para caber na pagina
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

    # Constroi o PDF
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
    Gera um XLSX com largura de coluna ajustada e cabecalho congelado.
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


# --- Rotas da API ---

@router.post("/analyze")
async def analyze_data(body: QueryRequest, db: AsyncConnection = Depends(get_db)):
    user_question = body.user_question
    db_schema = db_connection_string 
    
    # 2. Gere a resposta da IA (Bloqueante/Sincrona)
    # CORRECAO APLICADA: Chama a funcao sincrona de forma segura
    ai_response = await asyncio.to_thread(generate_ai_response, user_question, db_schema)
    
    # 3. Se nao ha query, retorna erro ou mensagem de texto
    if not ai_response.sql_query:
        return {
            "message": ai_response.message,
            "query": None,
            "data": None,
            "visualization_type": "text", 
            "x_axis": None, "y_axis": None, "label": None, "value": None,
        }
        
    # 4. Executa a query SQL AGORA ASSINCRONA
    # NOTA: execute_sql_query DEVE ser async def e receber 'db' como parametro,
    # caso contrario, esta linha tambem causaria um erro.
    data = await execute_sql_query(db, ai_response.sql_query) 
    
    # 5. Verifica se e um relatorio e retorna o arquivo apropriado
    if ai_response.visualization_type == "report":
        
        report_title = ai_response.message if ai_response.message else user_question

        if ai_response.report_type == "csv":
            # Retorna o arquivo CSV (Sincrono - usa asyncio.to_thread)
            return await asyncio.to_thread(generate_csv_response, data)
        
        elif ai_response.report_type == "pdf":
            # Retorna o arquivo PDF (Sincrono - usa asyncio.to_thread)
            return await asyncio.to_thread(generate_pdf_response, data, report_title)
        
        elif ai_response.report_type == "xlsx":
            # Retorna o arquivo XLSX (Sincrono - usa asyncio.to_thread)
            # CORRECAO: Necessita de 'await' aqui.
            return await asyncio.to_thread(generate_xlsx_response, data, report_title)
        
        # Se a IA pediu um relatorio, mas o formato nao e reconhecido, retorna JSON com os dados
        return {
            "message": f"Formato de relatorio '{ai_response.report_type}' nao suportado. Dados brutos retornados.",
            "query": ai_response.sql_query,
            "data": data,
            "visualization_type": "table",
            "x_axis": None, "y_axis": None, "label": None, "value": None,
        }
        
    # 6. Se nao for relatorio (grafico/tabela), retorna o JSON para o front-end
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

@router.get("/health/db")
async def health_db(db: AsyncConnection = Depends(get_db)):
    result = await db.execute(text("SELECT 1"))
    return {"db": (result.scalar() == 1)}

@router.get("/health/ai")
async def health_ai():
    try:
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        models = await asyncio.to_thread(genai.list_models)
        preferred = [
            "gemini-1.5-flash-latest",
            "gemini-1.5-flash",
            "gemini-1.5-pro-latest",
            "gemini-1.5-pro",
            "gemini-pro",
            "gemini-1.0-pro",
        ]
        available = [m.name for m in models if "generateContent" in getattr(m, "supported_generation_methods", [])]
        target = None
        for name in preferred:
            if name in available:
                target = name
                break
        if target is None and available:
            target = available[0]
        if not target:
            raise RuntimeError("Nenhum modelo disponivel para generateContent")
        model = genai.GenerativeModel(target)
        res = await asyncio.to_thread(lambda: model.generate_content("ping"))
        text = getattr(res, "text", None)
        ok = bool(text) or bool(getattr(res, "candidates", None))
        return {"ai": ok, "model": target}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
