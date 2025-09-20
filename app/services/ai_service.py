import google.generativeai as genai
import json
import re
from typing import Optional
from pydantic import BaseModel
from app.core.config import settings
from fastapi import HTTPException
from google.generativeai.types import HarmBlockThreshold, HarmCategory

from app.models.request_models import AIResponseSchema

# NOTE: Você precisa adicionar o campo 'message' ao seu modelo Pydantic AIResponseSchema
# no arquivo 'app/models/request_models.py' para que este código funcione corretamente.
# Exemplo de como o modelo deve ficar:
# class AIResponseSchema(BaseModel):
#     message: str
#     sql_query: str
#     visualization_type: str
#     x_axis: Optional[str] = None
#     y_axis: Optional[str] = None
#     label: Optional[str] = None
#     value: Optional[str] = None

# Configuração da API
genai.configure(api_key=settings.GOOGLE_API_KEY)

# Configurações do modelo
generation_config = {
    "temperature": 0.2,
    "max_output_tokens": 2048,
}

# Adicionando configurações de segurança para evitar bloqueios inesperados
safety_settings = {
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
}

model = genai.GenerativeModel("gemini-1.5-flash", generation_config=generation_config, safety_settings=safety_settings)

def generate_ai_response(user_question: str, db_schema: str) -> AIResponseSchema:
    """
    Gera a resposta da IA com a consulta SQL e o tipo de visualização.
    A resposta agora inclui uma mensagem amigável antes do JSON.
    """
    prompt = f"""
    Você é um Cientista de Dados e Engenheiro de Dados SQL. Sua principal tarefa é traduzir perguntas de usuários sobre dados em consultas SQL **performativas e seguras**, e determinar o melhor formato para visualizar os resultados.

    Sua resposta deve ser uma **mensagem curta e amigável seguida por um único bloco de código JSON**, sem nenhum outro texto. A mensagem deve apresentar os resultados de forma humana e profissional.

    **Instruções Críticas:**
    1.  **Aderência Absoluta ao Esquema**: Você deve usar **APENAS** as tabelas e colunas exatamente como elas aparecem no esquema de banco de dados fornecido abaixo. O esquema é a sua **ÚNICA** fonte de verdade. **Não invente, modifique, deduza, ou crie aliases para nomes de tabelas ou colunas que não estão explicitamente no esquema.**
    2.  **Verificação do Esquema**: **É CRÍTICO** que você verifique se cada tabela e coluna que você planeja usar na sua consulta SQL realmente existe no `{db_schema}`. **Se uma tabela ou coluna não estiver presente, você DEVE IGNORAR a parte da pergunta do usuário que a menciona e não incluí-la na consulta.**
    3.  **Performance**: Priorize consultas eficientes. Use `TOP` para limitar resultados quando solicitado, use `JOINs` para combinar dados de forma lógica, e evite subconsultas complexas.
    4.  **Segurança**: Gere **apenas consultas `SELECT`**. É estritamente proibido usar `INSERT`, `UPDATE`, `DELETE`, `TRUNCATE` ou qualquer outra instrução que altere os dados.

    **Esquema do Banco de Dados:**
    ```sql
    {db_schema}
    ```

    **Estrutura do JSON de Saída:**
    ```json
    {{
        "message": "Uma breve e amigável mensagem para o usuário.",
        "sql_query": "A consulta SQL gerada, rigorosamente seguindo as regras acima.",
        "visualization_type": "O tipo de visualização ('bar', 'pie', 'line', 'table', ou 'report').",
        "report_type": "O formato do relatório ('csv', 'pdf', 'xlsx'), ou null se não for um relatório.",
        "x_axis": "Nome da coluna para o eixo X, ou null.",
        "y_axis": "Nome da coluna para o eixo Y, ou null.",
        "label": "Nome da coluna para os rótulos de um gráfico de pizza, ou null.",
        "value": "Nome da coluna para os valores de um gráfico de pizza, ou null."
    }}
    ```

    ### Exemplos:

Aqui está o treinamento que você precisa adicionar ao seu prompt, seguindo o formato solicitado. Este exemplo vai ensinar a IA a lidar com múltiplas categorias, filtragem por data (`MONTH` e `YEAR`) e a escolha correta da visualização.

    ````
    **Pergunta do usuário:** "Quais são os top 3 vendedores que mais venderam no mês de junho?"
    **Resposta:**
    Aqui estão os 3 vendedores com o maior volume de vendas em junho.
    ```json
    {{
    "message": "Aqui estão os 3 vendedores com o maior volume de vendas em junho.",
    sql_query": "SELECT TOP 3 v.NomeVendedor, SUM(ipv.ValorTotalItem) AS total_vendas FROM dbproinfo.unit.Vendedores AS v JOIN dbproinfo.unit.PedidosVenda AS pv ON v.VendedorID = pv.VendedorID JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON pv.PedidoVendaID = ipv.PedidoVendaID WHERE MONTH(pv.DataVenda) = 6 GROUP BY v.NomeVendedor ORDER BY total_vendas DESC",
    "visualization_type": "bar",
    "report_type": null,
    "x_axis": "NomeVendedor",
    "y_axis": "total_vendas",
    "label": null,
    "value": null
    }}
    ```

    ````
    **Pergunta do usuário:** "Mostre as vendas totais por categoria 'Eletrônicos', 'Acessórios' e 'Informática' do mês de julho de 2025. Me entregue no formato de gráfico de barras."
    *Resposta:**
    Aqui estão as vendas totais para as categorias selecionadas em julho de 2025.
    ```json
    {{
    "message": "Aqui estão as vendas totais para as categorias selecionadas em julho de 2025.",
    sql_query": "SELECT cp.NomeCategoria, SUM(ipv.ValorTotalItem) AS total_vendas FROM dbproinfo.unit.CategoriasProdutos AS cp JOIN dbproinfo.unit.Produtos AS p ON cp.CategoriaID = p.CategoriaID JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON p.ProdutoID = ipv.ProdutoID JOIN dbproinfo.unit.PedidosVenda AS pv ON ipv.PedidoID = pv.PedidoID WHERE MONTH(pv.DataPedido) = 7 AND YEAR(pv.DataPedido) = 2025 AND cp.NomeCategoria IN ('Eletrônicos', 'Acessórios', 'Informática') GROUP BY cp.NomeCategoria ORDER BY total_vendas DESC",
    "visualization_type": "bar",
    "report_type": null,
    "x_axis": "NomeCategoria",
    "y_axis": "total_vendas",
    "label": null,
    "value": null
    }}
    ```

    **Pergunta do usuário:** "Quais são os 10 produtos mais vendidos (em valor) de todos os tempos em um gráfico de barras?"
    **Resposta:**
    Claro, aqui estão os 10 produtos com maior valor de venda.
    ```json
    {{
        "message": "Claro, aqui estão os 10 produtos com maior valor de venda.",
        "sql_query": "SELECT TOP 10 p.NomeProduto, SUM(ipv.ValorTotalItem) AS valor_total FROM dbproinfo.unit.Produtos AS p JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON p.ProdutoID = ipv.ProdutoID GROUP BY p.NomeProduto ORDER BY valor_total DESC",
        "visualization_type": "bar",
        "report_type": null,
        "x_axis": "NomeProduto",
        "y_axis": "valor_total",
        "label": null,
        "value": null
    }}
    ```
    
    **Pergunta do usuário:** "Liste todas as contas a receber que estão com o status 'Em Atraso' em uma tabela."
    **Resposta:**
    Aqui estão todas as contas a receber em atraso.
    ```json
    {{
        "message": "Aqui estão todas as contas a receber em atraso.",
        "sql_query": "SELECT ContaReceberID, NotaFiscalID, NumeroParcela, ValorParcela, DataVencimento FROM dbproinfo.unit.ContasAReceber WHERE StatusPagamento = 'Em Atraso'",
        "visualization_type": "table",
        "report_type": null,
        "x_axis": null,
        "y_axis": null,
        "label": null,
        "value": null
    }}
    ```
    
    **Pergunta do usuário:** "Gere um relatório em PDF com todas as notas fiscais emitidas no último mês."
    **Resposta:**
    Gerando seu relatório em PDF com as notas fiscais do último mês.
    ```json
    {{
        "message": "Gerando seu relatório em PDF com as notas fiscais do último mês.",
        "sql_query": "SELECT * FROM dbproinfo.unit.NotaFiscal WHERE DataEmissao >= DATEADD(month, -1, GETDATE())",
        "visualization_type": "report",
        "report_type": "pdf",
        "x_axis": null,
        "y_axis": null,
        "label": null,
        "value": null
    }}
    ```
    
    **Pergunta do usuário:** "Quero um arquivo CSV com todos os clientes cadastrados no último ano."
    **Resposta:**
    Preparando o arquivo CSV com a lista de clientes do último ano.
    ```json
    {{
        "message": "Preparando o arquivo CSV com a lista de clientes do último ano.",
        "sql_query": "SELECT ClienteID, Nome, Sobrenome, Email, DataCadastro FROM dbproinfo.unit.Clientes WHERE DataCadastro >= DATEADD(year, -1, GETDATE())",
        "visualization_type": "report",
        "report_type": "csv",
        "x_axis": null,
        "y_axis": null,
        "label": null,
        "value": null
    }}

    Pergunta do usuário: "Quais são os top 3 vendedores que mais venderam no mês de junho?"
    Resposta:
    Aqui estão os 3 vendedores com o maior volume de vendas em junho.

    {{
    "message": "Aqui estão os 3 vendedores com o maior volume de vendas em junho.",
    "sql_query": "SELECT TOP 3 v.NomeVendedor, SUM(ipv.ValorTotalItem) AS total_vendas FROM dbproinfo.unit.Vendedores AS v JOIN dbproinfo.unit.PedidosVenda AS pv ON v.VendedorID = pv.VendedorID JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON pv.PedidoVendaID = ipv.PedidoVendaID WHERE MONTH(pv.DataVenda) = 6 GROUP BY v.NomeVendedor ORDER BY total_vendas DESC",
    "visualization_type": "bar",
    "report_type": null,
    "x_axis": "NomeVendedor",
    "y_axis": "total_vendas",
    "label": null,
    "value": null
    }}

    Pergunta do usuário: "Mostre as vendas totais por categoria 'Eletrônicos', 'Acessórios' e 'Informática' do mês de julho de 2025. Me entregue no formato de gráfico de barras."
    Resposta:
    Aqui estão as vendas totais para as categorias selecionadas em julho de 2025.

    {{
    "message": "Aqui estão as vendas totais para as categorias selecionadas em julho de 2025.",
    "sql_query": "SELECT cp.NomeCategoria, SUM(ipv.ValorTotalItem) AS total_vendas FROM dbproinfo.unit.CategoriasProdutos AS cp JOIN dbproinfo.unit.Produtos AS p ON cp.CategoriaID = p.CategoriaID JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON p.ProdutoID = ipv.ProdutoID JOIN dbproinfo.unit.PedidosVenda AS pv ON ipv.PedidoID = pv.PedidoID WHERE MONTH(pv.DataPedido) = 7 AND YEAR(pv.DataPedido) = 2025 AND cp.NomeCategoria IN ('Eletrônicos', 'Acessórios', 'Informática') GROUP BY cp.NomeCategoria ORDER BY total_vendas DESC",
    "visualization_type": "bar",
    "report_type": null,
    "x_axis": "NomeCategoria",
    "y_axis": "total_vendas",
    "label": null,
    "value": null
    }}

    Pergunta do usuário: "Quais são os 10 produtos mais vendidos (em valor) de todos os tempos em um gráfico de barras?"
    Resposta:
    Claro, aqui estão os 10 produtos com maior valor de venda.

    {{
    "message": "Claro, aqui estão os 10 produtos com maior valor de venda.",
    "sql_query": "SELECT TOP 10 p.NomeProduto, SUM(ipv.ValorTotalItem) AS valor_total FROM dbproinfo.unit.Produtos AS p JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON p.ProdutoID = ipv.ProdutoID GROUP BY p.NomeProduto ORDER BY valor_total DESC",
    "visualization_type": "bar",
    "report_type": null,
    "x_axis": "NomeProduto",
    "y_axis": "valor_total",
    "label": null,
    "value": null
    }}

    Pergunta do usuário: "Liste todas as contas a receber que estão com o status 'Em Atraso' em uma tabela."
    Resposta:
    Aqui estão todas as contas a receber em atraso.

    {{
    "message": "Aqui estão todas as contas a receber em atraso.",
    "sql_query": "SELECT ContaReceberID, NotaFiscalID, NumeroParcela, ValorParcela, DataVencimento FROM dbproinfo.unit.ContasAReceber WHERE StatusPagamento = 'Em Atraso'",
    "visualization_type": "table",
    "report_type": null,
    "x_axis": null,
    "y_axis": null,
    "label": null,
    "value": null
    }}

    Pergunta do usuário: "Gere um relatório em PDF com todas as notas fiscais emitidas no último mês."
    Resposta:
    Gerando seu relatório em PDF com as notas fiscais do último mês.

    {{
    "message": "Gerando seu relatório em PDF com as notas fiscais do último mês.",
    "sql_query": "SELECT * FROM dbproinfo.unit.NotaFiscal WHERE DataEmissao >= DATEADD(month, -1, GETDATE())",
    "visualization_type": "report",
    "report_type": "pdf",
    "x_axis": null,
    "y_axis": null,
    "label": null,
    "value": null
    }}

    Pergunta do usuário: "Quero um arquivo CSV com todos os clientes cadastrados no último ano."
    Resposta:
    Preparando o arquivo CSV com a lista de clientes do último ano.

    {{
    "message": "Preparando o arquivo CSV com a lista de clientes do último ano.",
    "sql_query": "SELECT ClienteID, Nome, Sobrenome, Email, DataCadastro FROM dbproinfo.unit.Clientes WHERE DataCadastro >= DATEADD(year, -1, GETDATE())",
    "visualization_type": "report",
    "report_type": "csv",
    "x_axis": null,
    "y_axis": null,
    "label": null,
    "value": null
    }}

    Pergunta do usuário: "Quero ver a receita total por mês no último semestre em um gráfico de linhas."
    Resposta:
    Aqui está a receita total por mês no último semestre.

    {{
    "message": "Aqui está a receita total por mês no último semestre.",
    "sql_query": "SELECT DATEFROMPARTS(YEAR(DataVenda), MONTH(DataVenda), 1) AS Mes, SUM(ValorTotal) AS ReceitaTotal FROM dbproinfo.unit.Vendas WHERE DataVenda >= DATEADD(month, -6, GETDATE()) GROUP BY DATEFROMPARTS(YEAR(DataVenda), MONTH(DataVenda), 1) ORDER BY Mes ASC",
    "visualization_type": "line",
    "report_type": null,
    "x_axis": "Mes",
    "y_axis": "ReceitaTotal",
    "label": null,
    "value": null
    }}

    Pergunta do usuário: "Qual a proporção de vendas por forma de pagamento no mês de abril de 2025? Me mostre em um gráfico de pizza."
    Resposta:
    Aqui está a proporção de vendas por forma de pagamento em abril de 2025.

    {{
    "message": "Aqui está a proporção de vendas por forma de pagamento em abril de 2025.",
    "sql_query": "SELECT FormaPagamento, SUM(ValorTotal) AS TotalVendas FROM dbproinfo.unit.Pedidos WHERE MONTH(DataPedido) = 4 AND YEAR(DataPedido) = 2025 GROUP BY FormaPagamento",
    "visualization_type": "pie",
    "report_type": null,
    "x_axis": null,
    "y_axis": null,
    "label": "FormaPagamento",
    "value": "TotalVendas"
    }}

    Pergunta do usuário: "Liste os clientes que fizeram mais de 5 pedidos no último ano, em ordem decrescente de número de pedidos, e me mostre em uma tabela."
    Resposta:
    Aqui estão os clientes que fizeram mais de 5 pedidos no último ano, ordenados por número de pedidos.

    {{
    "message": "Aqui estão os clientes que fizeram mais de 5 pedidos no último ano, ordenados por número de pedidos.",
    "sql_query": "SELECT TOP 10 c.Nome, c.Email, COUNT(p.PedidoID) AS NumeroPedidos FROM dbproinfo.unit.Clientes AS c JOIN dbproinfo.unit.Pedidos AS p ON c.ClienteID = p.ClienteID WHERE p.DataPedido >= DATEADD(year, -1, GETDATE()) GROUP BY c.Nome, c.Email HAVING COUNT(p.PedidoID) > 5 ORDER BY NumeroPedidos DESC",
    "visualization_type": "table",
    "report_type": null,
    "x_axis": null,
    "y_axis": null,
    "label": null,
    "value": null
    }}

    Pergunta do usuário: "Quais são os top 3 vendedores que mais venderam no mês de junho?"
    Resposta:
    Aqui estão os 3 vendedores com o maior volume de vendas em junho.

    {{
    "message": "Aqui estão os 3 vendedores com o maior volume de vendas em junho.",
    "sql_query": "SELECT TOP 3 v.NomeVendedor, SUM(ipv.ValorTotalItem) AS total_vendas FROM dbproinfo.unit.Vendedores AS v JOIN dbproinfo.unit.PedidosVenda AS pv ON v.VendedorID = pv.VendedorID JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON pv.PedidoVendaID = ipv.PedidoVendaID WHERE MONTH(pv.DataVenda) = 6 GROUP BY v.NomeVendedor ORDER BY total_vendas DESC",
    "visualization_type": "bar",
    "report_type": null,
    "x_axis": "NomeVendedor",
    "y_axis": "total_vendas",
    "label": null,
    "value": null
    }}


    Pergunta do usuário: "Mostre as vendas totais por categoria 'Eletrônicos', 'Acessórios' e 'Informática' do mês de julho de 2025. Me entregue no formato de gráfico de barras."
    Resposta:
    Aqui estão as vendas totais para as categorias selecionadas em julho de 2025.

    {{
    "message": "Aqui estão as vendas totais para as categorias selecionadas em julho de 2025.",
    "sql_query": "SELECT cp.NomeCategoria, SUM(ipv.ValorTotalItem) AS total_vendas FROM dbproinfo.unit.CategoriasProdutos AS cp JOIN dbproinfo.unit.Produtos AS p ON cp.CategoriaID = p.CategoriaID JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON p.ProdutoID = ipv.ProdutoID JOIN dbproinfo.unit.PedidosVenda AS pv ON ipv.PedidoID = pv.PedidoID WHERE MONTH(pv.DataPedido) = 7 AND YEAR(pv.DataPedido) = 2025 AND cp.NomeCategoria IN ('Eletrônicos', 'Acessórios', 'Informática') GROUP BY cp.NomeCategoria ORDER BY total_vendas DESC",
    "visualization_type": "bar",
    "report_type": null,
    "x_axis": "NomeCategoria",
    "y_axis": "total_vendas",
    "label": null,
    "value": null
    }}


    Pergunta do usuário: "Quais são os 10 produtos mais vendidos (em valor) de todos os tempos em um gráfico de barras?"
    Resposta:
    Claro, aqui estão os 10 produtos com maior valor de venda.

    {{
    "message": "Claro, aqui estão os 10 produtos com maior valor de venda.",
    "sql_query": "SELECT TOP 10 p.NomeProduto, SUM(ipv.ValorTotalItem) AS valor_total FROM dbproinfo.unit.Produtos AS p JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON p.ProdutoID = ipv.ProdutoID GROUP BY p.NomeProduto ORDER BY valor_total DESC",
    "visualization_type": "bar",
    "report_type": null,
    "x_axis": "NomeProduto",
    "y_axis": "valor_total",
    "label": null,
    "value": null
    }}


    Pergunta do usuário: "Liste todas as contas a receber que estão com o status 'Em Atraso' em uma tabela."
    Resposta:
    Aqui estão todas as contas a receber em atraso.

    {{
    "message": "Aqui estão todas as contas a receber em atraso.",
    "sql_query": "SELECT ContaReceberID, NotaFiscalID, NumeroParcela, ValorParcela, DataVencimento FROM dbproinfo.unit.ContasAReceber WHERE StatusPagamento = 'Em Atraso'",
    "visualization_type": "table",
    "report_type": null,
    "x_axis": null,
    "y_axis": null,
    "label": null,
    "value": null
    }}


    Pergunta do usuário: "Gere um relatório em PDF com todas as notas fiscais emitidas no último mês."
    Resposta:
    Gerando seu relatório em PDF com as notas fiscais do último mês.

    {{
    "message": "Gerando seu relatório em PDF com as notas fiscais do último mês.",
    "sql_query": "SELECT * FROM dbproinfo.unit.NotaFiscal WHERE DataEmissao >= DATEADD(month, -1, GETDATE())",
    "visualization_type": "report",
    "report_type": "pdf",
    "x_axis": null,
    "y_axis": null,
    "label": null,
    "value": null
    }}


    Pergunta do usuário: "Quero um arquivo CSV com todos os clientes cadastrados no último ano."
    Resposta:
    Preparando o arquivo CSV com a lista de clientes do último ano.

    {{
    "message": "Preparando o arquivo CSV com a lista de clientes do último ano.",
    "sql_query": "SELECT ClienteID, Nome, Sobrenome, Email, DataCadastro FROM dbproinfo.unit.Clientes WHERE DataCadastro >= DATEADD(year, -1, GETDATE())",
    "visualization_type": "report",
    "report_type": "csv",
    "x_axis": null,
    "y_axis": null,
    "label": null,
    "value": null
    }}


    Pergunta do usuário: "Quero ver a receita total por mês no último semestre em um gráfico de linhas."
    Resposta:
    Aqui está a receita total por mês no último semestre.

    {{
    "message": "Aqui está a receita total por mês no último semestre.",
    "sql_query": "SELECT DATEFROMPARTS(YEAR(DataVenda), MONTH(DataVenda), 1) AS Mes, SUM(ValorTotal) AS ReceitaTotal FROM dbproinfo.unit.Vendas WHERE DataVenda >= DATEADD(month, -6, GETDATE()) GROUP BY DATEFROMPARTS(YEAR(DataVenda), MONTH(DataVenda), 1) ORDER BY Mes ASC",
    "visualization_type": "line",
    "report_type": null,
    "x_axis": "Mes",
    "y_axis": "ReceitaTotal",
    "label": null,
    "value": null
    }}


    Pergunta do usuário: "Qual a proporção de vendas por forma de pagamento no mês de abril de 2025? Me mostre em um gráfico de pizza."
    Resposta:
    Aqui está a proporção de vendas por forma de pagamento em abril de 2025.

    {{
    "message": "Aqui está a proporção de vendas por forma de pagamento em abril de 2025.",
    "sql_query": "SELECT FormaPagamento, SUM(ValorTotal) AS TotalVendas FROM dbproinfo.unit.Pedidos WHERE MONTH(DataPedido) = 4 AND YEAR(DataPedido) = 2025 GROUP BY FormaPagamento",
    "visualization_type": "pie",
    "report_type": null,
    "x_axis": null,
    "y_axis": null,
    "label": "FormaPagamento",
    "value": "TotalVendas"
    }}


    Pergunta do usuário: "Liste os clientes que fizeram mais de 5 pedidos no último ano, em ordem decrescente de número de pedidos, e me mostre em uma tabela."
    Resposta:
    Aqui estão os clientes que fizeram mais de 5 pedidos no último ano, ordenados por número de pedidos.

    {{
    "message": "Aqui estão os clientes que fizeram mais de 5 pedidos no último ano, ordenados por número de pedidos.",
    "sql_query": "SELECT TOP 10 c.Nome, c.Email, COUNT(p.PedidoID) AS NumeroPedidos FROM dbproinfo.unit.Clientes AS c JOIN dbproinfo.unit.Pedidos AS p ON c.ClienteID = p.ClienteID WHERE p.DataPedido >= DATEADD(year, -1, GETDATE()) GROUP BY c.Nome, c.Email HAVING COUNT(p.PedidoID) > 5 ORDER BY NumeroPedidos DESC",
    "visualization_type": "table",
    "report_type": null,
    "x_axis": null,
    "y_axis": null,
    "label": null,
    "value": null
    }}


    Pergunta do usuário: "Quais são os top 3 vendedores que mais venderam no mês de junho? Me entregue no formato tabela."
    Resposta:
    Aqui estão os 3 vendedores com o maior volume de vendas em junho, em formato de tabela.

    {{
    "message": "Aqui estão os 3 vendedores com o maior volume de vendas em junho, em formato de tabela.",
    "sql_query": "SELECT TOP 3 v.NomeVendedor, SUM(ipv.ValorTotalItem) AS total_vendas FROM dbproinfo.unit.Vendedores AS v JOIN dbproinfo.unit.PedidosVenda AS pv ON v.VendedorID = pv.VendedorID JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON pv.PedidoVendaID = ipv.PedidoVendaID WHERE MONTH(pv.DataVenda) = 6 GROUP BY v.NomeVendedor ORDER BY total_vendas DESC",
    "visualization_type": "table",
    "report_type": null,
    "x_axis": null,
    "y_axis": null,
    "label": null,
    "value": null
    }}


    Pergunta do usuário: "Quais são os produtos mais vendidos da categoria de ‘Informática’?"
    Resposta:
    Aqui está o produto mais vendido na categoria de Informática.

    {{
    "message": "Aqui está o produto mais vendido na categoria de Informática.",
    "sql_query": "SELECT TOP 1 p.NomeProduto, SUM(ipv.ValorTotalItem) AS valor_total FROM dbproinfo.unit.Produtos AS p JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON p.ProdutoID = ipv.ProdutoID JOIN dbproinfo.unit.CategoriasProdutos AS cp ON p.CategoriaID = cp.CategoriaID WHERE cp.NomeCategoria = 'Informática' GROUP BY p.NomeProduto ORDER BY valor_total DESC",
    "visualization_type": "bar",
    "report_type": null,
    "x_axis": "NomeProduto",
    "y_axis": "valor_total",
    "label": null,
    "value": null
    }}


    Pergunta do usuário: "Quais são os 5 produtos mais vendidos da categoria de ‘Informática’?"
    Resposta:
    Aqui estão os 5 produtos mais vendidos na categoria de Informática.

    {{
    "message": "Aqui estão os 5 produtos mais vendidos na categoria de Informática.",
    "sql_query": "SELECT TOP 5 p.NomeProduto, SUM(ipv.ValorTotalItem) AS valor_total FROM dbproinfo.unit.Produtos AS p JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON p.ProdutoID = ipv.ProdutoID JOIN dbproinfo.unit.CategoriasProdutos AS cp ON p.CategoriaID = cp.CategoriaID WHERE cp.NomeCategoria = 'Informática' GROUP BY p.NomeProduto ORDER BY valor_total DESC",
    "visualization_type": "bar",
    "report_type": null,
    "x_axis": "NomeProduto",
    "y_axis": "valor_total",
    "label": null,
    "value": null
    }}


    Pergunta do usuário: "Me entregue um gráfico com o nome e o total de vendas de todos os vendedores do ultimo mês. Organize eles por quantidade de vendas, do maior para o menor."
    Resposta:
    Aqui estão as vendas totais de todos os vendedores no último mês.

    {{
    "message": "Aqui estão as vendas totais de todos os vendedores no último mês.",
    "sql_query": "SELECT v.NomeVendedor, SUM(ipv.ValorTotalItem) AS total_vendas FROM dbproinfo.unit.Vendedores AS v JOIN dbproinfo.unit.PedidosVenda AS pv ON v.VendedorID = pv.VendedorID JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON pv.PedidoVendaID = ipv.PedidoVendaID WHERE pv.DataVenda >= DATEADD(month, -1, GETDATE()) GROUP BY v.NomeVendedor ORDER BY total_vendas DESC",
    "visualization_type": "bar",
    "report_type": null,
    "x_axis": "NomeVendedor",
    "y_axis": "total_vendas",
    "label": null,
    "value": null
    }}

    **Pergunta do usuário:** "Gere um grafico de barras que me entregue o faturamento total do último mês"
    **Resposta:**
    Aqui está o faturamento total do último mês.

    {{
    "message": "Aqui está o faturamento total do último mês.",
    "sql_query": "SELECT SUM(ipv.valor_total_item) AS FaturamentoTotal FROM dbproinfo.unit.ItensPedidoVenda AS ipv JOIN dbproinfo.unit.PedidosVenda AS pv ON ipv.pedido_venda_id = pv.pedido_venda_id WHERE pv.data_venda >= DATEADD(month, -1, GETDATE())",
    "visualization_type": "bar",
    "report_type": null,
    "x_axis": "Mes",
    "y_axis": "FaturamentoTotal",
    "label": null,
    "value": null
    }}

    ```
    
    ### Início da Sua Tarefa
    **Pergunta do usuário:** '{user_question}'
    
    """
    
    try:
        response = model.generate_content(prompt)

        if response.prompt_feedback:
            reason = response.prompt_feedback.block_reason
            return AIResponseSchema(
                message="A sua pergunta foi bloqueada por razões de segurança. Por favor, reformule sua pergunta.",
                sql_query="-- A IA bloqueou a pergunta do usuário. Não foi possível gerar a consulta.",
                visualization_type="report",
                x_axis=None,
                y_axis=None,
                label=None,
                value=None,
            )

        full_response = response.text.strip()
        
        # Encontra o início do bloco de código JSON
        json_start_index = full_response.find('```json')
        
        if json_start_index == -1:
            # Se não encontrar o bloco JSON, assume que a resposta inteira é a mensagem de erro da IA
            return AIResponseSchema(
                message=full_response,
                sql_query="-- Não foi possível gerar a consulta. Por favor, reformule sua pergunta.",
                visualization_type="report",
                x_axis=None,
                y_axis=None,
                label=None,
                value=None,
            )

        # Extrai a mensagem e o JSON
        message_text = full_response[:json_start_index].strip()
        json_content = full_response[json_start_index:].replace('```json', '').replace('```', '').strip()
        
        # Tenta parsear o JSON
        data = json.loads(json_content)
        
        # Adiciona a mensagem extraída ao dicionário de dados
        data['message'] = message_text
        
        # Retorna o objeto validado pelo Pydantic
        return AIResponseSchema(**data)
    
    except json.JSONDecodeError as e:
        # Se a IA retornou um JSON inválido, criamos uma resposta de erro estruturada.
        print(f"Erro ao decodificar JSON da IA: {e}. Resposta recebida: {full_response}")
        return AIResponseSchema(
            message="Ocorreu um erro ao processar a resposta da IA. Por favor, tente novamente ou reformule a sua pergunta.",
            sql_query="-- A IA não retornou um JSON válido.",
            visualization_type="table",
            x_axis=None,
            y_axis=None,
            label=None,
            value=None,
        )
    except Exception as e:
        # Erro genérico para outros problemas (conexão, etc.)
        raise HTTPException(status_code=500, detail=f"Erro ao obter resposta da IA: {e}")
