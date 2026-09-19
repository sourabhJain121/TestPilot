from pydantic import BaseModel, Field
from typing import List

class GeneratedTestCase(BaseModel):
    test_name: str = Field(..., description="Descriptive test name prefixed with test_")
    category: str = Field(..., description="boundary, null_check, or edge_case")
    reasoning: str = Field(..., description="Step-by-step reasoning linking spec to assertion")
    code: str = Field(..., description="Complete executable pytest code block")

class TestSuiteModel(BaseModel):
    test_cases: List[GeneratedTestCase]
