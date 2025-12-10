# chroma_manager.py
import chromadb
from chromadb.config import Settings
import json
from typing import List, Dict
import hashlib
import uuid

class RiskChromaManager:
    def __init__(self, persist_directory: str = "./chroma_db"):
        """Инициализация ChromaDB"""
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False)
        )
        
        # Коллекция для рисков
        self.collection = self.client.get_or_create_collection(
            name="contract_risks",
            metadata={"description": "Риски договоров подряда"}
        )
    
    def add_risks_from_json(self, json_path: str = "data/risks.json"):
        """Добавляет риски из JSON в ChromaDB"""
        print("📦 Загружаю риски в ChromaDB...")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            risks = json.load(f)
        
        documents = []
        metadatas = []
        ids = []
        
        for risk in risks:
            # Формируем документ для поиска
            doc_text = self._create_document_text(risk)
            
            # Создаем уникальный ID
            risk_id = risk.get("id", str(uuid.uuid4()))
            
            # Метаданные для фильтрации
            metadata = {
                "risk_id": risk_id,
                "category": risk["metadata"]["risk_category"],
                "severity": risk["metadata"]["severity"],
                "articles": ",".join(risk["metadata"]["relevant_articles"]),
                "header": risk["header"],
                "source": "КонсультантПлюс"
            }
            
            documents.append(doc_text)
            metadatas.append(metadata)
            ids.append(risk_id)
        
        # Добавляем в ChromaDB
        self.collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        print(f"✅ Добавлено {len(risks)} рисков в ChromaDB")
        return len(risks)
    
    def _create_document_text(self, risk: Dict) -> str:
        """Создает текст для эмбеддинга"""
        parts = [
            f"Заголовок: {risk['header']}",
            f"Описание: {risk['metadata']['description']}",
            f"Что не так: {risk['metadata'].get('pattern', '')}",
            f"Рекомендация: {risk['metadata']['recommendation']}",
            f"Последствия: {'; '.join(risk['metadata']['consequences'])}",
            f"Статьи ГК РФ: {'; '.join(risk['metadata']['relevant_articles'])}",
            f"Тело риска: {risk['body'][:500]}"
        ]
        return "\n".join(parts)
    
    def search_risks(self, query: str, n_results: int = 5, category: str = None):
        """Ищет риски по запросу"""
        
        # Параметры поиска
        where_filter = {}
        if category:
            where_filter["category"] = category
        
        results = self.collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter if where_filter else None
        )
        
        return self._format_results(results)
    
    def _format_results(self, results):
        """Форматирует результаты поиска"""
        formatted = []
        
        for i in range(len(results['ids'][0])):
            formatted.append({
                "id": results['ids'][0][i],
                "score": results['distances'][0][i],
                "document": results['documents'][0][i][:300] + "...",
                "metadata": results['metadatas'][0][i]
            })
        
        return formatted
    
    def get_statistics(self):
        """Статистика коллекции"""
        count = self.collection.count()
        return {
            "total_risks": count,
            "collection_name": "contract_risks"
        }