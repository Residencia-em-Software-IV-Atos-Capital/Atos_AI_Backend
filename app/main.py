from fastapi import FastAPI
from app.routes import data_routes # type: ignore

app = FastAPI()

# Inclui os endpoints do seu router
app.include_router(data_routes.router)

@app.get("/")
def read_root():
    return {"message": "API de BI com IA. Use o endpoint /analyze para começar."}