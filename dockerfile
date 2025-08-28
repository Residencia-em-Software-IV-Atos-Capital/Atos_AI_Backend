# Imagem base oficial do Python
FROM python:3.11-slim

# Variável de ambiente para não interagir com apt
ENV DEBIAN_FRONTEND=noninteractive

# Instalar dependências e ODBC Driver
RUN apt-get update && apt-get install -y curl gnupg2 apt-transport-https unixodbc-dev \
    && curl https://packages.microsoft.com/keys/microsoft.asc | apt-key add - \
    && curl https://packages.microsoft.com/config/debian/11/prod.list | tee /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql17 \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependências Python
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar o código
COPY . .

# Comando para iniciar a API FastAPI
CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8000"]
