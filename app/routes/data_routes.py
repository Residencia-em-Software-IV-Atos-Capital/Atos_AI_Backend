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

# Importações do ReportLab
from reportlab.lib.pagesizes import letter, A4 
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
import re # Módulo regex

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
    """Gera um PDF robusto."""
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
    """Gera um XLSX com largura de coluna ajustada e cabeçalho congelado."""
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
# --- NOVAS ROTAS ESTÁTICAS (GET) SEM USO DE IA (Atualizadas para PostgreSQL) ---
# -----------------------------------------------------------------

## 🔑 Rota Estática para KPI
@router.get("/kpi/static")
async def get_static_kpi(db: AsyncSession = Depends(get_db)):
    """
    Retorna 3 KPIs: Total de vendas no mês, Quantidade produtos vendidos, e Ticket médio.
    Corrigido para PostgreSQL.
    """
    static_query = """
    WITH MonthlySales AS (
    -- Total de Vendas no Mês
    SELECT SUM(valortotal) AS total_sales
    FROM unit.pedidosvenda
    -- Condição de Mês Corrente
    WHERE TO_CHAR(datapedido::date, 'YYYY-MM') = TO_CHAR(NOW()::date, 'YYYY-MM')
    ),
    TotalItemsSold AS (
    -- Quantidade de Produtos Vendidos no Mês
    SELECT SUM(t2.quantidade) AS total_items
    FROM unit.pedidosvenda t1
    -- CORREÇÃO FINAL: Usando a chave primária correta 't1.pedidoid' 
    -- para se ligar à chave estrangeira 't2.pedidoid'
    JOIN unit.itenspedidovenda t2 ON t1.pedidoid = t2.pedidoid 
    WHERE TO_CHAR(t1.datapedido::date, 'YYYY-MM') = TO_CHAR(NOW()::date, 'YYYY-MM')
    ),
    AverageTicket AS (
    -- Ticket Médio (média do valor total dos pedidos no mês)
    SELECT AVG(valortotal) AS avg_ticket
    FROM unit.pedidosvenda
    WHERE TO_CHAR(datapedido::date, 'YYYY-MM') = TO_CHAR(NOW()::date, 'YYYY-MM')
    )
    SELECT 
    COALESCE((SELECT total_sales FROM MonthlySales), 0) AS total_vendas_mes,
    COALESCE((SELECT total_items FROM TotalItemsSold), 0) AS quantidade_produtos_vendidos,
    COALESCE((SELECT avg_ticket FROM AverageTicket), 0) AS ticket_medio;
    """
    
    data = await execute_sql_query(db, static_query)
    
    kpi_values = {}
    if data and isinstance(data[0], dict):
        kpi_values = data[0]

    return {
        "type": "kpi",
        "status": "success",
        "message": "KPIs Estáticos: Vendas do Mês, Produtos Vendidos e Ticket Médio.",
        "query": static_query,
        "kpis": kpi_values,
        "data": data # Retorna os dados brutos também
    }


## 📊 Rota Estática para Gráfico de Barras
@router.get("/bar/static")
async def get_static_bar_chart(db: AsyncSession = Depends(get_db)):
    """
    Retorna dados estáticos para Gráfico de Barras: Vendas nos meses daquele ano.
    Corrigido para PostgreSQL.
    """
    # Query SQL estática: Vendas por mês no ano atual (PostgreSQL)
    static_query = """
    SELECT 
        TO_CHAR(datapedido::date, 'YYYY-MM') AS month_label, 
        SUM(valortotal) AS total_sales
    FROM unit.pedidosvenda
    WHERE 
        TO_CHAR(datapedido::date, 'YYYY') = TO_CHAR(NOW()::date, 'YYYY')
    GROUP BY month_label
    ORDER BY month_label;
    """
    
    data = await execute_sql_query(db, static_query)

    return {
        "type": "bar",
        "status": "success",
        "message": "Gráfico Estático: Vendas Totais nos Meses do Ano Atual",
        "query": static_query,
        "data": data,
        "x_axis": "Mês/Ano",
        "y_axis": "Total de Vendas",
    }


## 🍕 Rota Estática para Gráfico de Pizza
@router.get("/pie/static")
async def get_static_pie_chart(db: AsyncSession = Depends(get_db)):
    """
    Retorna dados estáticos para Gráfico de Pizza: Os 5 melhores clientes (maior valor comprado).
    Também inclui dados para Vendedores (quem vendeu mais, decrescente).
    Corrigido para PostgreSQL (minúsculas).
    """
    # Query SQL estática 1: Top 5 Clientes por Valor Comprado (PostgreSQL)
    top_clients_query = """
        SELECT
            c.nome AS client_name, 
            SUM(o.valortotal) AS value_purchased,
            COUNT(o.pedidoid) AS total_orders -- CORREÇÃO: Usando a PK correta da tabela pedidosvenda
        FROM unit.pedidosvenda o
        -- CORREÇÃO: Trocando c.id por c.clienteid
        JOIN unit.clientes c ON o.clienteid = c.clienteid 
        GROUP BY c.nome
        ORDER BY value_purchased DESC
        LIMIT 5;
        """
    
    # Query SQL estática 2: Vendedores por Valor Total Vendido (Decrescente) (PostgreSQL)
    top_sellers_query = """
    SELECT
        e.nomecompleto AS seller_name, -- CORREÇÃO: Usando 'nomecompleto' que é a coluna que contém o nome do vendedor
        SUM(o.valortotal) AS total_sold
    FROM unit.pedidosvenda o
    -- CORREÇÃO: Trocando e.id por e.vendedorid
    JOIN unit.vendedores e ON o.vendedorid = e.vendedorid
    GROUP BY e.nomecompleto -- CORREÇÃO: Agrupando pelo nome correto da coluna
    ORDER BY total_sold DESC;
    """
    
    top_clients_data = await execute_sql_query(db, top_clients_query)
    top_sellers_data = await execute_sql_query(db, top_sellers_query)

    return {
        "type": "pie",
        "status": "success",
        "message": "Gráfico Estático: Top 5 Clientes e Vendedores por Performance",
        "queries": {
            "top_clients": top_clients_query,
            "top_sellers": top_sellers_query,
        },
        "data_clients": top_clients_data, # Dados dos 5 melhores clientes
        "data_sellers": top_sellers_data, # Dados dos vendedores
        "client_labels": {"name": "client_name", "value": "value_purchased", "count": "total_orders"},
        "seller_labels": {"name": "seller_name", "value": "total_sold"},
    }


## 🔎 Rota de Análise Original (Inalterada)
@router.post("/analyze")
async def analyze_data(body: QueryRequest, db: AsyncSession = Depends(get_db)): 
    user_question = body.user_question
    db_schema = db_connection_string 
    
    # 2. Gere a resposta da IA (Bloqueante/Síncrona)
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
        
    # 4. Executa a query SQL
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