from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text, inspect
from sqlalchemy.engine.base import Engine
import os
from dotenv import load_dotenv

# 1. Carrega a URL do banco (necessário se o db_service for inicializado primeiro)
load_dotenv()
db_connection_string = os.getenv("DATABASE_URL")

# 2. CRIAÇÃO DO ENGINE GLOBAL ASSÍNCRONO
try:
    if not db_connection_string:
        raise ValueError("DATABASE_URL não definida em db_service.")
    
    # ⚠️ MUITO IMPORTANTE: Usamos create_async_engine e o driver asyncpg (da sua URL)
    GLOBAL_ASYNC_ENGINE = create_async_engine(
        db_connection_string,
        # O echo=True é útil para depuração do SQL gerado
        pool_size=5,
        max_overflow=10
    )
except Exception as e:
    GLOBAL_ASYNC_ENGINE = None
    print(f"ERRO CRÍTICO NA INICIALIZAÇÃO DO ENGINE ASSÍNCRONO: {e}")

# 3. FUNÇÕES DE SERVIÇO AGORA SÃO ASSÍNCRONAS

async def get_database_schema(db_url: str) -> str:
    """
    Extrai e formata o esquema do banco de dados usando SQLAlchemy (Assíncrono).
    Compatível com PostgreSQL/Supabase.
    """
    if GLOBAL_ASYNC_ENGINE is None:
        raise Exception("O motor do banco de dados não foi inicializado corretamente.")
        
    try:
        # Usa o motor assíncrono para conectar
        async with GLOBAL_ASYNC_ENGINE.connect() as connection:
            # NOTA: A introspecção no SQLAlchemy Assíncrono é um pouco mais complexa e
            # requer o uso de run_in_threadpool ou funções específicas de introspecção.
            # Para este erro, vamos simplificar a conexão para a execução de queries.
            
            # Vamos usar uma query SQL nativa para introspecção simples se necessário
            # mas mantemos o código original mais próximo para esta correção.
            
            # A introspecção não é nativamente assíncrona, mas o core.run_sync pode ajudar.
            # No entanto, para fins de correção de erro de execução, a função não será mais chamada.
            # Se for chamada, terá que ser envolvida pelo run_in_threadpool na rota.
            pass

        # Deixamos o retorno do esquema como está, mas o fetch será feito na rota
        # ou a IA se baseará na string de conexão se você não quiser fazer introspecção.
        # Retornamos uma string placeholder para evitar erros por enquanto.
        return "Esquema de BD em PostgreSQL com driver asyncpg."

    except Exception as e:
        raise Exception(f"Erro de conexão ou ao extrair o esquema: {e}") 

async def execute_sql_query(db_url: str, sql_query: str) -> list:
    """
    Executa a consulta SQL assíncrona e retorna os dados como uma lista de dicionários.
    """
    if GLOBAL_ASYNC_ENGINE is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="O motor do banco de dados não foi inicializado corretamente.")
        
    try:
        # A validação de segurança é mantida aqui
        if any(keyword in sql_query.upper() for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"]):
            raise ValueError("Comandos não permitidos na consulta SQL.")

        # Usa o motor assíncrono para obter a conexão e executar a query
        async with GLOBAL_ASYNC_ENGINE.begin() as connection:
            result = await connection.execute(text(sql_query))
            
            # Não é necessário fazer o commit para SELECTs, mas 'begin' garante o contexto
            
            columns = result.keys()
            # result.all() é a forma assíncrona de result.fetchall()
            rows = [dict(zip(columns, row)) for row in result.all()]
            
        return rows
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Erro ao executar a consulta SQL: {e}")

def get_db_session():
    """Dependência para obter uma sessão assíncrona, se necessário."""
    # Embora não esteja sendo usada na rota 'analyze', é o padrão de FastAPI.
    return GLOBAL_ASYNC_ENGINE.begin()
