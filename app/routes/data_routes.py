# app/routes/data_routes.py

import os
import io
import re
import pandas as pd
from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.models.request_models import QueryRequest
from app.services.ai_service import generate_ai_response
from app.services.db_service import execute_sql_query

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

load_dotenv()

# Conexão
db_connection_string = os.getenv("DATABASE_URL")
if not db_connection_string:
    raise ValueError("A variável de ambiente 'DATABASE_URL' não está definida.")

router = APIRouter()



def _safe_filename(name: str) -> str:
    name = (name or "report").strip().lower()
    name = re.sub(r"[^a-z0-9_\-\.]+", "_", name)
    return (name or "report")[:80]


def generate_csv_response(data: list, filename: str = "report.csv") -> StreamingResponse:
    df = pd.DataFrame(data or [])
    csv_io = io.StringIO()
    # Se quiser, pode personalizar quando vazio. Aqui exporta header (se houver) e/ou nada.
    df.to_csv(csv_io, index=False)
    bytes_io = io.BytesIO(csv_io.getvalue().encode("utf-8-sig"))
    bytes_io.seek(0)
    return StreamingResponse(
        bytes_io,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={_safe_filename(filename)}"}
    )


def generate_pdf_response(data: list, title: str) -> StreamingResponse:
    """
    Gera um PDF robusto:
    - Ajusta largura das colunas para caber na página
    - Repete cabeçalho em cada página
    - Trata dataset vazio
    """
    df = pd.DataFrame(data or [])
    buffer = io.BytesIO()

    # Página e margens
    page_size = A4  # ou 'letter'
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
    avg_char_width = font_size_body * 0.55  # aproximação em points

    # mede comprimento máximo (em caracteres) por coluna (com limite)
    max_chars_per_col = []
    sample_rows = rows[:1000]
    for j in range(len(headers)):
        max_len = len(headers[j])
        for r in sample_rows:
            if j < len(r):
                l = len(r[j] or "")
                if l > max_len:
                    max_len = l
        max_chars_per_col.append(min(max_len, 40))  # cap em 40 chars

    raw_widths = [max(50, m * avg_char_width + 12) for m in max_chars_per_col]  # min 50pt
    scale = min(1.0, available_width / sum(raw_widths))
    col_widths = [w * scale for w in raw_widths]

    table = Table(table_data, colWidths=col_widths, repeatRows=1, splitByRow=1)

    table_style = TableStyle([
        # Cabeçalho
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),

        # Corpo
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


@router.post("/analyze")
async def analyze_data(body: QueryRequest):
    """
    - Chama a IA
    - Executa a SQL
    - Se for report: devolve o arquivo na hora (PDF/CSV/XLSX)
    - Caso contrário: retorna JSON com dados
    """
    user_question = body.user_question
    db_schema = db_connection_string

    try:
        ai_response = generate_ai_response(user_question, db_schema)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar pergunta com IA: {e}")

    # Se não há SQL, devolve mensagem de texto
    if not ai_response.sql_query:
        return {
            "message": ai_response.message,
            "query": None,
            "data": None,
            "visualization_type": "text",
            "x_axis": None, "y_axis": None, "label": None, "value": None,
        }

    # Executa consulta
    try:
        data = execute_sql_query(db_connection_string, ai_response.sql_query)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao executar consulta: {e}")

    # Se for relatório: baixa direto
    if (ai_response.visualization_type or "").lower() == "report":
        report_type = (ai_response.report_type or "pdf").lower().strip()
        report_type = {"excel": "xlsx"}.get(report_type, report_type)  # normaliza

        report_title = ai_response.message or user_question or "Relatório BI"

        if report_type == "csv":
            return generate_csv_response(data, filename=f"{_safe_filename(report_title)}.csv")
        elif report_type == "pdf":
            return generate_pdf_response(data, report_title)
        elif report_type == "xlsx":
            return generate_xlsx_response(data, report_title)
        else:
            # Desconhecido: devolve JSON
            return {
                "message": f"Formato de relatório '{ai_response.report_type}' não suportado. Dados brutos retornados.",
                "query": ai_response.sql_query,
                "data": data,
                "visualization_type": "table",
                "x_axis": None, "y_axis": None, "label": None, "value": None,
            }

    # Não é relatório: retorna JSON
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