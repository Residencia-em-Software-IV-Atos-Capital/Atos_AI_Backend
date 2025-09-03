from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from app.models.request_models import QueryRequest
from app.services.ai_service import generate_ai_response
from app.services.db_service import execute_sql_query
import pandas as pd
import io

router = APIRouter()

@router.post("/analyze")
async def analyze_data(body: QueryRequest, request: Request):
    db_schema = request.app.state.db_schema
    ai_response = generate_ai_response(body.user_question, db_schema)
    
    data = execute_sql_query(ai_response.sql_query)
    
    return {
        "data": data,
        "visualization_type": ai_response.visualization_type,
        "x_axis": ai_response.x_axis,
        "y_axis": ai_response.y_axis,
        "label": ai_response.label,
        "value": ai_response.value,
    }


@router.post("/report/csv")
async def get_csv_report(body: QueryRequest, request: Request):

    db_schema = request.app.state.db_schema
    ai_response = generate_ai_response(body.user_question, db_schema)
    
    data = execute_sql_query(ai_response.sql_query)

    df = pd.DataFrame(data)
    buffer = io.StringIO()
    df.to_csv(buffer, index=False)
    buffer.seek(0)
    
    return StreamingResponse(
        buffer, 
        media_type="text/csv", 
        headers={"Content-Disposition": "attachment;filename=report.csv"}
    )