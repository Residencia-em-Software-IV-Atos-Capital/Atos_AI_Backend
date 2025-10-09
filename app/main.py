from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from app.routes import data_routes

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,                      
    allow_credentials=True,                     
    allow_methods=["*"],                        
    allow_headers=["*"],                        
)
# Inclui os endpoints do seu router
app.include_router(data_routes.router)

@app.get("/")
def read_root():
    return {"message": "API de BI com IA. Use o endpoint /analyze para começar."}