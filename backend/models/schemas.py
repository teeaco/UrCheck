from pydantic import BaseModel, Field
from typing import Optional

class DocumentAnalysisResponse(BaseModel):

    success: bool = Field(
        ...,
        description="Успешно ли обработан файл"
    )

    file_name: str = Field(
        ...,
        description="Имя загруженного файла",
        min_length=1,
        max_length=255
    )
    
    result_text: str = Field(
        ...,
        description="Результат анализа от LLM",
        min_length=1  
    )

    message: Optional[str] = Field(
        None,
        description="Дополнительное сообщение",
        max_length=500
    )

    class Config:
        # json_schema_extra добавляет пример в автоматическую документацию (Swagger UI)
        json_schema_extra = {
            "example": {
                "success": True,
                "file_name": "document.docx",
                "result_text": "блаблабла",
                "message": "Документ успешно проанализирован"
            }
        }