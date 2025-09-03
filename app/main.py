from fastapi import FastAPI
from app.routes import data_routes
import uvicorn
from dotenv import load_dotenv
from app.services.db_service import get_database_schema 

app = FastAPI()


# Inclui os endpoints do seu router
app.include_router(data_routes.router)
app.state.db_schema = get_database_schema()

@app.get("/")
def read_root():
    return {"message": "API de BI com IA. Use o endpoint /analyze para começar."}

if __name__ == "__main__":    
    load_dotenv() 
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=True)