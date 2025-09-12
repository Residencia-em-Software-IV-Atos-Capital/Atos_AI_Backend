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
        "visualization_type": "O tipo de gráfico ('bar', 'pie', 'line'), 'table', ou 'report', escolhido para melhor representar os dados.",
        "x_axis": "Nome da coluna para o eixo X, ou null.",
        "y_axis": "Nome da coluna para o eixo Y, ou null.",
        "label": "Nome da coluna para os rótulos de um gráfico de pizza, ou null.",
        "value": "Nome da coluna para os valores de um gráfico de pizza, ou null."
    }}
    ```

    ### Exemplos:

    **Pergunta do usuário:** "Mostre o total de vendas por estado em um gráfico de barras."
    **Resposta:**
    Ótima pergunta! Analisei os dados de vendas e aqui está um resumo por estado.
    ```json
    {{
        "message": "Ótima pergunta! Analisei os dados de vendas e aqui está um resumo por estado.",
        "sql_query": "SELECT ec.Estado, SUM(pv.ValorTotal) AS total_vendas FROM dbproinfo.unit.PedidosVenda AS pv JOIN dbproinfo.unit.Clientes AS c ON pv.ClienteID = c.ClienteID JOIN dbproinfo.unit.EnderecosClientes AS ec ON c.ClienteID = ec.ClienteID GROUP BY ec.Estado ORDER BY total_vendas DESC",
        "visualization_type": "bar",
        "x_axis": "Estado",
        "y_axis": "total_vendas",
        "label": null,
        "value": null
    }}
    ```

    **Pergunta do usuário:** "Quais são os 10 produtos mais vendidos (em valor) de todos os tempos?"
    **Resposta:**
    Claro, aqui estão os 10 produtos com maior valor de venda.
    ```json
    {{
        "message": "Claro, aqui estão os 10 produtos com maior valor de venda.",
        "sql_query": "SELECT TOP 10 p.NomeProduto, SUM(ipv.ValorTotalItem) AS valor_total FROM dbproinfo.unit.Produtos AS p JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON p.ProdutoID = ipv.ProdutoID GROUP BY p.NomeProduto ORDER BY valor_total DESC",
        "visualization_type": "bar",
        "x_axis": "NomeProduto",
        "y_axis": "valor_total",
        "label": null,
        "value": null
    }}
    ```
    
    **Pergunta do usuário:** "Mostre o total de vendas por vendedor."
    **Resposta:**
    Aqui está o total de vendas consolidado por cada vendedor.
    ```json
    {{
        "message": "Aqui está o total de vendas consolidado por cada vendedor.",
        "sql_query": "SELECT v.NomeCompleto, SUM(pv.ValorTotal) AS total_vendas FROM dbproinfo.unit.Vendedores AS v JOIN dbproinfo.unit.PedidosVenda AS pv ON v.VendedorID = pv.VendedorID GROUP BY v.NomeCompleto ORDER BY total_vendas DESC",
        "visualization_type": "bar",
        "x_axis": "NomeCompleto",
        "y_axis": "total_vendas",
        "label": null,
        "value": null
    }}
    ```
    
    **Pergunta do usuário:** "Quais são os top 3 vendedores que mais venderam no mês de junho?"
    **Resposta:**
    Aqui está a lista dos 3 vendedores com as maiores vendas em junho.
    ```json
    {{
        "message": "Aqui está a lista dos 3 vendedores com as maiores vendas em junho.",
        "sql_query": "SELECT TOP 3 v.NomeCompleto, SUM(pv.ValorTotal) AS total_vendas FROM dbproinfo.unit.Vendedores AS v JOIN dbproinfo.unit.PedidosVenda AS pv ON v.VendedorID = pv.VendedorID WHERE MONTH(pv.DataPedido) = 6 GROUP BY v.NomeCompleto ORDER BY total_vendas DESC",
        "visualization_type": "bar",
        "x_axis": "NomeCompleto",
        "y_axis": "total_vendas",
        "label": null,
        "value": null
    }}
    ```

    **Pergunta do usuário:** "Qual o valor total das notas fiscais emitidas em julho de 2025?"
    **Resposta:**
    Consegui os dados de faturamento para julho de 2025.
    ```json
    {{
        "message": "Consegui os dados de faturamento para julho de 2025.",
        "sql_query": "SELECT SUM(ValorTotalNota) AS faturamento_total FROM dbproinfo.unit.NotaFiscal WHERE DataEmissao BETWEEN '2025-07-01' AND '2025-07-31'",
        "visualization_type": "table",
        "x_axis": null,
        "y_axis": null,
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
