# -*- coding: utf-8 -*-
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import data_routes

app = FastAPI()

# Configuracao de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # ou ["http://localhost:3000"] se preferir restringir
    allow_credentials=True,
    allow_methods=["*"],          # permite GET, POST, OPTIONS, etc.
    allow_headers=["*"],          # permite Content-Type, Authorization, etc.
)

# Inclui o router
app.include_router(data_routes.router)

@app.get("/")
def read_root():
    return {"message": "API de BI com IA. Use o endpoint /analyze para comecar."}
