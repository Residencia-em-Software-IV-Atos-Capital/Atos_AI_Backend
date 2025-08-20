import google.generativeai as genai
import json
from app.core.config import settings
from app.models.request_models import AIResponseSchema
from fastapi import HTTPException

# Configuração da API
genai.configure(api_key=settings.GOOGLE_API_KEY)

# Configurações do modelo
generation_config = {
    "temperature": 0.2,
    "max_output_tokens": 2048,
}
model = genai.GenerativeModel("gemini-pro", generation_config=generation_config)

def generate_ai_response(user_question: str, db_schema: str) -> AIResponseSchema:
    """
    Gera a resposta da IA com a consulta SQL e tipo de visualização.
    """
    prompt = f"""
    Sua tarefa é traduzir a pergunta de um usuário em uma consulta SQL válida e também determinar a melhor forma de visualizar os dados.

    O banco de dados tem o seguinte esquema:
    {db_schema}

    Forneça a resposta em um formato JSON. O JSON deve ter as seguintes chaves:
    'sql_query': A consulta SQL que extrai os dados necessários.
    'visualization_type': Tipo de gráfico ('bar', 'pie', 'line') ou 'table' ou 'report'.
    'x_axis': Coluna para o eixo X. Nulo para 'table', 'pie', ou 'report'.
    'y_axis': Coluna para o eixo Y. Nulo para 'table', 'pie', ou 'report'.
    'label': Coluna para os rótulos de um gráfico de pizza. Nulo se não for 'pie'.
    'value': Coluna para os valores de um gráfico de pizza. Nulo se não for 'pie'.

    Pergunta do usuário: '{user_question}'
    """
    try:
        response = model.generate_content(prompt)
        ai_output = response.text.strip()
        data = json.loads(ai_output)
        return AIResponseSchema(**data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao obter resposta da IA: {e}")