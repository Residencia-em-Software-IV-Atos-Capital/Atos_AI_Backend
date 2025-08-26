import google.generativeai as genai
import json
from app.core.config import settings
from app.models.request_models import AIResponseSchema
from fastapi import HTTPException
from google.generativeai.types import HarmBlockThreshold, HarmCategory

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
    Gera a resposta da IA com a consulta SQL e tipo de visualização.
    """
    # O prompt permanece o mesmo, pois a IA já está gerando o JSON corretamente.
    prompt = f"""
    Sua tarefa é traduzir a pergunta de um usuário em uma consulta SQL válida e também determinar o melhor formato para visualizar os dados.

    Sua resposta deve ser APENAS um objeto JSON válido, sem qualquer texto ou formatação adicional.

    O banco de dados tem o seguinte esquema, com os nomes completos das tabelas:
    {db_schema}

    A consulta SQL deve usar apenas comandos 'SELECT'. Não utilize 'INSERT', 'UPDATE', 'DELETE' ou outros comandos que alterem o banco de dados.

    O JSON de saída deve ter as seguintes chaves:
    - "sql_query": A consulta SQL gerada.
    - "visualization_type": O tipo de gráfico ('bar', 'pie', 'line'), 'table', ou 'report'.
    - "x_axis": Nome da coluna para o eixo X. Use `null` para 'table', 'pie', ou 'report'.
    - "y_axis": Nome da coluna para o eixo Y. Use `null` para 'table', 'pie', ou 'report'.
    - "label": Nome da coluna para os rótulos de um gráfico de pizza. Use `null` se não for 'pie'.
    - "value": Nome da coluna para os valores de um gráfico de pizza. Use `null` se não for 'pie'.

    A seguir, alguns exemplos de perguntas e o JSON de saída esperado.

    ### Exemplos:

    Pergunta do usuário: "Mostre o total de vendas por estado em um gráfico de barras."
    {{
        "sql_query": "SELECT ec.Estado, SUM(pv.ValorTotal) AS total_vendas FROM dbproinfo.unit.PedidosVenda AS pv JOIN dbproinfo.unit.Clientes AS c ON pv.ClienteID = c.ClienteID JOIN dbproinfo.unit.EnderecosClientes AS ec ON c.ClienteID = ec.ClienteID GROUP BY ec.Estado ORDER BY total_vendas DESC",
        "visualization_type": "bar",
        "x_axis": "Estado",
        "y_axis": "total_vendas",
        "label": null,
        "value": null
    }}
    
    Pergunta do usuário: "Quais são os 10 produtos mais vendidos (em valor) de todos os tempos?"
    {{
        "sql_query": "SELECT TOP 10 p.NomeProduto, SUM(ipv.ValorTotalItem) AS valor_total FROM dbproinfo.unit.Produtos AS p JOIN dbproinfo.unit.ItensPedidoVenda AS ipv ON p.ProdutoID = ipv.ProdutoID GROUP BY p.NomeProduto ORDER BY valor_total DESC",
        "visualization_type": "bar",
        "x_axis": "NomeProduto",
        "y_axis": "valor_total",
        "label": null,
        "value": null
    }}
    
    Pergunta do usuário: "Qual o valor total das notas fiscais emitidas em julho de 2025?"
    {{
        "sql_query": "SELECT SUM(ValorTotalNota) AS faturamento_total FROM dbproinfo.unit.NotaFiscal WHERE DataEmissao BETWEEN '2025-07-01' AND '2025-07-31'",
        "visualization_type": "table",
        "x_axis": null,
        "y_axis": null,
        "label": null,
        "value": null
    }}

    ### Fim dos Exemplos

    Pergunta do usuário: '{user_question}'
    """
    try:
        response = model.generate_content(prompt)

        if response.prompt_feedback:
            reason = response.prompt_feedback.block_reason
            return AIResponseSchema(
                sql_query="-- A IA bloqueou a pergunta do usuário. Não foi possível gerar a consulta.",
                visualization_type="report",
                x_axis=None,
                y_axis=None,
                label=None,
                value=None,
            )
            
        ai_output = response.text.strip()
        
        # LINHA MODIFICADA AQUI: Remove os blocos de código Markdown antes de decodificar o JSON.
        ai_output = ai_output.replace('```json', '').replace('```', '')

        # Tenta parsear o JSON
        data = json.loads(ai_output)
        
        # Retorna o objeto validado pelo Pydantic
        return AIResponseSchema(**data)
    
    except json.JSONDecodeError as e:
        # Se a IA retornou um JSON inválido, criamos uma resposta de erro estruturada.
        print(f"Erro ao decodificar JSON da IA: {e}. Resposta recebida: {ai_output}")
        return AIResponseSchema(
            sql_query="-- A IA não retornou um JSON válido. Por favor, reformule a sua pergunta.",
            visualization_type="table",
            x_axis=None,
            y_axis=None,
            label=None,
            value=None,
        )
    except Exception as e:
        # Erro genérico para outros problemas (conexão, etc.)
        raise HTTPException(status_code=500, detail=f"Erro ao obter resposta da IA: {e}")