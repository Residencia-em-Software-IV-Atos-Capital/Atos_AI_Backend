import uvicorn
import os
from dotenv import load_dotenv

if __name__ == "__main__":
    load_dotenv()  # Carrega as variáveis de ambiente do arquivo .env
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)