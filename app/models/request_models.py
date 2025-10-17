from pydantic import BaseModel
from typing import Optional

class QueryRequest(BaseModel):
    user_question: str
    # db_connection_string: str

class AIResponseSchema(BaseModel):
    message: str
    sql_query: str | None
    visualization_type: Optional[str] | None
    report_type: Optional[str] = None  # <-- NOVO CAMPO
    x_axis: Optional[str] = None 
    y_axis: Optional[str] = None 
    label: Optional[str] = None 
    value: Optional[str] = None 