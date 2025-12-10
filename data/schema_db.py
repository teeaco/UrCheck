# db_schema.py
import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class RiskLevel(str, Enum):
    LOW = "низкий"
    MEDIUM = "средний" 
    HIGH = "высокий"
    CRITICAL = "критический"

class DocumentType(str, Enum):
    SUPPLIER = "supplier"
    CUSTOMER = "customer"
    CONTRACTOR = "contractor"
    SERVICES_LEGAL = "services_legal"
    SERVICES_INDIVIDUAL = "services_individual"

@dataclass
class RiskEntry: #Структура для хранения риска в векторной БД
    id: str
    risk_title: str
    header: str
    summary: str
    full_text: str
    risk_category: str
    relevant_articles: List[str]
    consequences: List[str]
    recommendation: str
    severity: int  # 1-10
    document_type: DocumentType
    source_file: str
    metadata: Dict[str, Any] = None
    
    def to_dict(self):
        data = asdict(self)
        data["search_text"] = self._create_search_text()
        return data
    
    def _create_search_text(self):
        """Создает объединенный текст для поиска"""
        parts = [
            self.risk_title,
            self.header,
            self.summary,
            " ".join(self.relevant_articles),
            " ".join(self.consequences),
            self.recommendation
        ]
        return " ".join(parts)

@dataclass
class NormEntry:
    """Структура для хранения норм ГК в векторной БД"""
    id: str
    article_number: str
    header: str
    text: str
    summary: str
    keywords: List[str]
    law_type: str = "ГК РФ"
    
    def to_dict(self):
        data = asdict(self)
        data["search_text"] = self._create_search_text()
        return data
    
    def _create_search_text(self):
        parts = [
            f"Статья {self.article_number} ГК РФ",
            self.header,
            self.text,
            " ".join(self.keywords)
        ]
        return " ".join(parts)

@dataclass 
class ConnectionEntry:
    """Связи между рисками и нормами"""
    risk_id: str
    norm_id: str
    article_number: str
    strength: float = 1.0  # Сила связи (можно вычислять)