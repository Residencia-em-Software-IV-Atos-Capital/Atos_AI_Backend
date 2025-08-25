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

model = genai.GenerativeModel("gemini-2.5-flash", generation_config=generation_config, safety_settings=safety_settings)

def generate_ai_response(user_question: str, db_schema: str) -> AIResponseSchema:
    """
    Gera a resposta da IA com a consulta SQL e tipo de visualização.
    """
    # Seu prompt (as instruções para a IA)
    prompt = """
    Você é um especialista em SQL e em visualização de dados. Sua tarefa é traduzir a pergunta de um usuário em uma consulta SQL válida e também determinar o melhor formato para visualizar os dados.

    A sua resposta deve ser APENAS um objeto JSON válido, sem qualquer texto adicional, explicações, ou formatação antes ou depois.

    O banco de dados tem o seguinte esquema de tabelas:
    {db_schema}

    A consulta SQL deve usar apenas comandos 'SELECT'. O uso de 'INSERT', 'UPDATE' e 'DELETE' é estritamente proibido.

    Forneça a resposta em um formato JSON com as seguintes chaves:
    - **sql_query**: A consulta SQL para extrair os dados.
    - **visualization_type**: O tipo de visualização a ser usado ('bar', 'pie', 'line', 'table', ou 'report').
    - **x_axis**: O nome da coluna para o eixo X. Use `null` para 'table', 'pie', ou 'report'.
    - **y_axis**: O nome da coluna para o eixo Y. Use `null` para 'table', 'pie', ou 'report'.
    - **label**: O nome da coluna para os rótulos em um gráfico de pizza. Use `null` se não for 'pie'.
    - **value**: O nome da coluna para os valores em um gráfico de pizza. Use `null` se não for 'pie'.

    Pergunta do usuário: '{user_question}'
    """
    try:
        response = model.generate_content(prompt)

        # Se a resposta foi bloqueada, use a informação do prompt_feedback para criar a mensagem.
        if response.prompt_feedback:
            reason = response.prompt_feedback.block_reason
            return AIResponseSchema(
                sql_query="-- Não foi possível gerar a consulta. ",
                visualization_type="report",
                x_axis=None,
                y_axis=None,
                label=None,
                value=None,
                description=f"A pergunta foi bloqueada pela IA. Motivo: {reason.name}"
            )
            
        ai_output = response.text.strip()
        
        # Tenta parsear o JSON
        data = json.loads(ai_output)
        
        # Retorna o objeto validado pelo Pydantic
        return AIResponseSchema(**data)
    
    except json.JSONDecodeError as e:
        # Se a IA retornou um JSON inválido (provavelmente uma string vazia)
        # nós criamos nossa própria resposta JSON.
        return AIResponseSchema(
            sql_query="-- Não foi possível gerar a consulta. ",
            visualization_type="report",
            x_axis=None,
            y_axis=None,
            label=None,
            value=None,
            description=f"A IA não retornou uma resposta válida."
        )

    except Exception as e:
        # Erro genérico para outros problemas (conexão, etc.)
        raise HTTPException(status_code=500, detail=f"Erro ao obter resposta da IA: {e}")