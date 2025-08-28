#!/bin/bash
set -e  # Para parar se qualquer comando falhar

echo "Atualizando pacotes..."
sudo apt-get update -y

echo "Instalando dependências para ODBC Driver..."
sudo apt-get install -y curl apt-transport-https gnupg2 software-properties-common unixodbc-dev

echo "Adicionando repositório Microsoft para ODBC Driver 17..."
curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -
curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list | sudo tee /etc/apt/sources.list.d/mssql-release.list

echo "Atualizando pacotes novamente..."
sudo apt-get update -y

echo "Instalando ODBC Driver 17 para SQL Server..."
sudo ACCEPT_EULA=Y apt-get install -y msodbcsql17

echo "Instalando pip se não estiver presente..."
sudo apt-get install -y python3-pip

echo "Instalando dependências do Python..."
pip3 install --upgrade pip
pip3 install -r requirements.txt

echo "Executando a aplicação..."
python3 run.py
