import os
from fastapi import HTTPException, Depends
from sqlalchemy import text, inspect
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

# --- CONFIGURAÇÃO ASSÍNCRONA (FEITA UMA ÚNICA VEZ) ---

# 1. Carrega a string de conexão do ambiente.
db_connection_string = os.getenv("DATABASE_URL")
if not db_connection_string:
    raise ValueError("A variável de ambiente 'DATABASE_URL' não está definida.")

# 2. Cria o "engine" assíncrono. Ele gerencia as conexões com o banco.
engine = create_async_engine(
    db_connection_string, 
    pool_pre_ping=True,
    pool_size=5,         # Um número base seguro
    max_overflow=2  )

# 3. Cria um "fabricante de sessão" para criar novas sessões para cada requisição.
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# --- DEPENDÊNCIA E SERVIÇOS ---

async def get_db() -> AsyncSession:
    """
    Dependência do FastAPI para gerenciar a sessão do banco de dados.
    Abre uma sessão, a disponibiliza para a rota e garante que seja fechada no final.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_database_schema(db: AsyncSession = Depends(get_db)) -> str:
    """
    Extrai e formata o esquema do banco de dados de forma assíncrona.
    """
    def _get_schema_sync(connection):
        # Esta função interna contém a lógica síncrona original.
        inspector = inspect(connection)
        
        # Para PostgreSQL, o schema padrão é 'public'. Ajuste se o seu for diferente.
        # Se você precisa do schema 'unit' como no original, use-o aqui.
        table_names = inspector.get_table_names(schema='public')
        schema_string = ""
        
        for table_name in table_names:
            # Para PostgreSQL, o nome completo geralmente é `schema.tabela`
            full_table_name = f"public.{table_name}"
            schema_string += f"Tabela `{full_table_name}`:\n"
            
            columns = inspector.get_columns(table_name, schema='public')
            
            for column in columns:
                column_type = str(column['type']).upper()
                schema_string += f"- `{column['name']}` ({column_type})\n"
            schema_string += "\n"
            
        return schema_string

    try:
        # Usamos run_sync para executar a função síncrona de inspeção em um thread separado, sem bloquear.
        schema = await db.run_sync(_get_schema_sync)
        return schema
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Erro de conexão ou ao extrair o esquema: {e}")


async def execute_sql_query(db: AsyncSession, sql_query: str) -> list[dict]:
    """
    Executa a consulta SQL de forma assíncrona e retorna os dados como uma lista de dicionários.
    """
    try:
        # Validação de segurança é mantida.
        if any(keyword in sql_query.upper() for keyword in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE"]):
            raise ValueError("Comandos não permitidos na consulta SQL.")

        # Executa a query usando a sessão assíncrona com 'await'.
        result = await db.execute(text(sql_query))
        
        # .mappings().all() é a forma moderna e eficiente de obter uma lista de dicionários.
        rows = result.mappings().all()
        
        return rows
    except ValueError as ve: # Captura o erro de validação separadamente
        raise HTTPException(status_code=403, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao executar a consulta SQL: {e}")