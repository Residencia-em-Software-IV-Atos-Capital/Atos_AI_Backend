# Imagem base oficial do Python
FROM python:3.11-slim


# Instalar dependências e ODBC Driver
RUN apt-get update && apt-get install -y freetds-dev freetds-bin
RUN pip install pymssql

# Instalar dependências Python
WORKDIR /app
COPY . .

ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código
COPY . .

# Comando para iniciar a API FastAPI
CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8000"]