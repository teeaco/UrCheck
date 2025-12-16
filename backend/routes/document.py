from fastapi import APIRouter, File, UploadFile, HTTPException, status, Depends
from pathlib import Path

from services.file_handler import FileHandler
from services.auth import AuthService
from services.llm_service import analyze_document
from models.schemas import DocumentAnalysisResponse

from dependencies import get_db
from services.auth import AuthService
from models.user import User
from config.setting import settings

router = APIRouter(
    prefix="/api",
    tags=["documents"],
    responses={404: {"description": "Not found"}},
)

file_handler = FileHandler()

@router.get("/")
async def get_documents(current_user: User = Depends(AuthService.get_current_user)):
    current_user: User = Depends(AuthService.get_current_user),
    db: Session = Depends(get_db)
    return {
        "message": "Ваши документы",
        "user": current_user.username,
        "user_id": current_user.id
    }

@router.post(
    "/upload",
    response_model=DocumentAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Загрузить и проанализировать документ",
    description="Загружает файл .docx, извлекает текст и отправляет на анализ LLM",
)
async def upload_and_analyze_document(file: UploadFile = File(...)) -> DocumentAnalysisResponse:
    
    try:
        file_content = await file.read()
        
        print(f"Получен файл: {file.filename} ({len(file_content)} байт)")

        is_valid, error_message = file_handler.validate_file(
            file.filename,
            len(file_content)
        )
        
        if not is_valid:
            print(f"Ошибка валидации: {error_message}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        print(f"Файл валиден")
        
        file_path: Path = file_handler.save_uploaded_file(
            file_content,
            file.filename
        )
        
        print(f"Файл сохранён: {file_path}")
        
        document_text: str = file_handler.extract_text_from_docx(file_path)
        
        print(f"Текст извлечён ({len(document_text)} символов)")
        
        if not document_text.strip():
            file_handler.cleanup_file(file_path)
            print(f"Ошибка: документ пуст")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Документ пуст или не содержит текста"
            )
        
        analysis_result: str = await analyze_document(document_text)
        
        print(f"Анализ LLM завершён")
        
        file_handler.cleanup_file(file_path)
        
        print(f"Файл удалён")
        
        response = DocumentAnalysisResponse(
            success=True,
            file_name=file.filename,
            result_text=analysis_result,
            message="Документ успешно проанализирован"
        )
        
        print(f"Ответ готов\n")
        
        return response
    
    except HTTPException:
        raise
    
    except Exception as e:
        print(f"Неожиданная ошибка: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при обработке документа: {str(e)}"
        )