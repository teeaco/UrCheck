import os
from pathlib import Path
from docx import Document
from config.setting import settings

class FileHandler:
    
    @staticmethod
    def validate_file(filename: str, file_size: int) -> tuple[bool, str]:
        
        file_extension = filename.split('.')[-1].lower()
        
        if file_extension not in settings.ALLOWED_EXTENSIONS:
            allowed = ", ".join(settings.ALLOWED_EXTENSIONS)
            error_message = f"Недопустимое расширение файла. Разрешены: {allowed}"
            return False, error_message
        
        if file_size > settings.MAX_FILE_SIZE:
            max_size_mb = settings.MAX_FILE_SIZE / (1024 * 1024)
            error_message = f"Файл слишком большой. Максимум {max_size_mb:.0f} MB"
            return False, error_message
        
        return True, ""
    
    @staticmethod
    def save_uploaded_file(file_content: bytes, filename: str) -> Path:
        
        try:
            safe_filename = "".join(
                c for c in filename 
                if c.isalnum() or c in (' ', '.', '-', '_')
            )
            
            if not safe_filename:
                safe_filename = "document.docx"

            file_path = settings.UPLOAD_DIR / safe_filename
            
            with open(file_path, 'wb') as f:
                f.write(file_content)
            
            return file_path
        
        except Exception as e:
            raise Exception(f"Ошибка при сохранении файла: {str(e)}")
    
    @staticmethod
    def extract_text_from_docx(file_path: Path) -> str:
       
        try:
            doc = Document(file_path)
            text_content = []
            
            for paragraph in doc.paragraphs:

                paragraph_text = paragraph.text.strip()
                if paragraph_text:
                    text_content.append(paragraph_text)
            
            full_text = "\n".join(text_content)
            
            return full_text
        
        except Exception as e:
            raise Exception(f"Ошибка при чтении файла: {str(e)}")
    
    
    @staticmethod
    def cleanup_file(file_path: Path) -> None:
        try:
            if file_path.exists():
                os.remove(file_path)
        
        except Exception as e:
            print(f"Ошибка при удалении файла: {str(e)}")
