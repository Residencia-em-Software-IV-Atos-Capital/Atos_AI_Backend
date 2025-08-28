from pydantic import BaseModel
from typing import Optional

class QueryRequest(BaseModel):
    user_question: str
    # db_connection_string: str

class AIResponseSchema(BaseModel):
    sql_query: str
    visualization_type: Optional[str]
    x_axis: Optional[str]
    y_axis: Optional[str]
    label: Optional[str]
    value: Optional[str]