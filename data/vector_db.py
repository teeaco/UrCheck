# vector_db.py
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional, Union
import json
import re

class ContractRiskDB:
    """
    Векторная база данных для хранения рисков, норм ГК и связей между ними.
    
    Основные возможности:
    1. Хранение рисков из документов КонсультантПлюс
    2. Хранение норм Гражданского кодекса РФ
    3. Связи между рисками и нормами
    4. Семантический поиск по всем данным
    """
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        """
        Инициализация базы данных.
        
        Args:
            persist_directory: Папка для хранения данных ChromaDB
        """
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        self._initialize_collections()
    
    def _initialize_collections(self):
        """Инициализирует коллекции базы данных"""
        # Коллекция рисков
        self.risks = self.client.get_or_create_collection(
            name="risks",
            metadata={
                "description": "База рисков из аналитических материалов КонсультантПлюс",
                "source": "Готовые решения КонсультантПлюс 2025"
            }
        )
        
        # Коллекция норм ГК РФ
        self.norms = self.client.get_or_create_collection(
            name="norms",
            metadata={
                "description": "Статьи Гражданского кодекса РФ",
                "source": "ГК РФ с изменениями на 2025 год"
            }
        )
        
        # Коллекция связей (для быстрых JOIN-запросов)
        self.connections = self.client.get_or_create_collection(
            name="connections",
            metadata={
                "description": "Связи между рисками и нормами ГК РФ",
                "relationship": "risk <-> norm"
            }
        )
    
    # ============ МЕТОДЫ ДЛЯ РИСКОВ ============
    
    def add_risks(self, risks: List[Dict]) -> int:
        """
        Добавляет риски в базу данных.
        
        Args:
            risks: Список словарей с рисками
            
        Returns:
            Количество добавленных рисков
        """
        ids = []
        documents = []
        metadatas = []
        
        for risk in risks:
            # Создаем текстовое представление для семантического поиска
            doc_text = self._create_risk_document(risk)
            
            ids.append(risk['id'])
            documents.append(doc_text)
            
            # Структурированные метаданные
            metadata = {
                "type": "risk",
                "risk_id": risk['id'],
                "title": risk['metadata']['risk_title'],
                "category": risk['metadata']['risk_category'],
                "severity": risk['metadata']['severity'],
                "source_doc": risk['metadata']['document_type'],
                "source_file": risk['metadata']['source_file'],
                "articles": "|".join(risk['metadata']['relevant_articles']),
                "consequences": "|".join(risk['metadata']['consequences']),
                "recommendation": risk['metadata']['recommendation'][:300]
            }
            metadatas.append(metadata)
        
        self.risks.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        
        return len(risks)
    
    def search_risks(self, query: str, n_results: int = 10, **filters) -> List[Dict]:
        """
        Поиск рисков по семантическому запросу.
        
        Args:
            query: Текстовый запрос
            n_results: Количество результатов
            filters: Дополнительные фильтры (category, severity_min, severity_max, etc.)
            
        Returns:
            Список найденных рисков с метаданными
        """
        # Строим условия where для фильтрации
        where_clause = self._build_where_clause(filters)
        
        results = self.risks.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause
        )
        
        return self._format_results(results)
    
    def get_risk_by_id(self, risk_id: str) -> Optional[Dict]:
        """
        Получает риск по его ID.
        
        Args:
            risk_id: ID риска
            
        Returns:
            Риск или None если не найден
        """
        try:
            result = self.risks.get(ids=[risk_id])
            if result['ids']:
                return {
                    'id': result['ids'][0],
                    'metadata': result['metadatas'][0],
                    'document': result['documents'][0]
                }
        except:
            pass
        return None
    
    def get_risks_by_category(self, category: str, limit: int = 50) -> List[Dict]:
        """
        Получает все риски определенной категории.
        
        Args:
            category: Категория риска
            limit: Максимальное количество
            
        Returns:
            Список рисков
        """
        results = self.risks.get(
            where={"category": category},
            limit=limit
        )
        return self._format_results(results)
    
    def get_all_categories(self) -> List[str]:
        """
        Возвращает все уникальные категории рисков.
        
        Returns:
            Список категорий
        """
        categories = set()
        results = self.risks.get(limit=1000)  # Получаем достаточно для анализа
        
        for metadata in results.get('metadatas', []):
            if 'category' in metadata:
                categories.add(metadata['category'])
        
        return sorted(list(categories))
    
    # ============ МЕТОДЫ ДЛЯ НОРМ ============
    
    def add_norms(self, norms: List[Dict]) -> int:
        """
        Добавляет нормы ГК РФ в базу данных.
        
        Args:
            norms: Список норм
            
        Returns:
            Количество добавленных норм
        """
        ids = []
        documents = []
        metadatas = []
        
        for norm in norms:
            # Создаем текстовое представление
            doc_text = self._create_norm_document(norm)
            
            ids.append(norm['id'])
            documents.append(doc_text)
            
            metadata = {
                "type": "norm",
                "norm_id": norm['id'],
                "article_number": norm['metadata']['article'],
                "keywords": "|".join(norm['metadata']['keywords']),
                "law_type": norm['metadata']['law_type']
            }
            metadatas.append(metadata)
        
        self.norms.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )
        
        return len(norms)
    
    def search_norms(self, query: str, n_results: int = 10, **filters) -> List[Dict]:
        """
        Поиск норм по семантическому запросу.
        
        Args:
            query: Текстовый запрос
            n_results: Количество результатов
            filters: Дополнительные фильтры
            
        Returns:
            Список найденных норм
        """
        where_clause = self._build_where_clause(filters)
        
        results = self.norms.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause
        )
        
        return self._format_results(results)
    
    def get_norm_by_article(self, article_number: str) -> Optional[Dict]:
        """
        Получает норму по номеру статьи.
        
        Args:
            article_number: Номер статьи
            
        Returns:
            Норма или None
        """
        results = self.norms.get(
            where={"article_number": article_number}
        )
        
        if results['ids']:
            return {
                'id': results['ids'][0],
                'metadata': results['metadatas'][0],
                'document': results['documents'][0]
            }
        return None
    
    def get_norms_by_keyword(self, keyword: str, limit: int = 20) -> List[Dict]:
        """
        Ищет нормы по ключевому слову.
        
        Args:
            keyword: Ключевое слово
            limit: Максимальное количество
            
        Returns:
            Список норм
        """
        # Ищем в документах и метаданных
        results = self.norms.get(limit=limit)
        filtered = []
        
        for i, doc in enumerate(results.get('documents', [])):
            if keyword.lower() in doc.lower():
                filtered.append({
                    'id': results['ids'][i],
                    'metadata': results['metadatas'][i],
                    'document': doc
                })
        
        return filtered
    
    # ============ МЕТОДЫ ДЛЯ СВЯЗЕЙ ============
    
    def add_connections(self, connections: Dict) -> int:
        """
        Добавляет связи между рисками и нормами.
        
        Args:
            connections: Словарь связей из connections.json
            
        Returns:
            Количество добавленных связей
        """
        ids = []
        documents = []
        metadatas = []
        
        added_count = 0
        
        # risk_to_norms
        for risk_id, norm_ids in connections.get('risk_to_norms', {}).items():
            for norm_id in norm_ids:
                # Извлекаем номер статьи из ID нормы
                article_num = self._extract_article_number(norm_id)
                
                connection_id = f"conn_{risk_id}_{norm_id}"
                doc_text = f"Связь между риском {risk_id} и статьей {article_num} ГК РФ"
                
                ids.append(connection_id)
                documents.append(doc_text)
                metadatas.append({
                    "type": "connection",
                    "risk_id": risk_id,
                    "norm_id": norm_id,
                    "article_number": article_num,
                    "direction": "risk_to_norm"
                })
                added_count += 1
        
        # norm_to_risks
        for norm_id, risk_ids in connections.get('norm_to_risks', {}).items():
            for risk_id in risk_ids:
                article_num = self._extract_article_number(norm_id)
                
                connection_id = f"conn_{risk_id}_{norm_id}_rev"
                doc_text = f"Связь между статьей {article_num} ГК РФ и риском {risk_id}"
                
                ids.append(connection_id)
                documents.append(doc_text)
                metadatas.append({
                    "type": "connection",
                    "risk_id": risk_id,
                    "norm_id": norm_id,
                    "article_number": article_num,
                    "direction": "norm_to_risk"
                })
                added_count += 1
        
        if ids:
            self.connections.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
        
        return added_count
    
    def get_risks_for_norm(self, norm_id: str) -> List[Dict]:
        """
        Получает все риски, связанные с нормой.
        
        Args:
            norm_id: ID нормы
            
        Returns:
            Список рисков
        """
        results = self.connections.get(
            where={"norm_id": norm_id, "direction": "norm_to_risk"}
        )
        
        risk_ids = []
        for metadata in results.get('metadatas', []):
            risk_ids.append(metadata['risk_id'])
        
        # Получаем риски по ID
        if risk_ids:
            risks_data = self.risks.get(ids=risk_ids)
            return self._format_results(risks_data)
        
        return []
    
    def get_norms_for_risk(self, risk_id: str) -> List[Dict]:
        """
        Получает все нормы, связанные с риском.
        
        Args:
            risk_id: ID риска
            
        Returns:
            Список норм
        """
        results = self.connections.get(
            where={"risk_id": risk_id, "direction": "risk_to_norm"}
        )
        
        norm_ids = []
        for metadata in results.get('metadatas', []):
            norm_ids.append(metadata['norm_id'])
        
        # Получаем нормы по ID
        if norm_ids:
            norms_data = self.norms.get(ids=norm_ids)
            return self._format_results(norms_data)
        
        return []
    
    def get_related_risks(self, risk_id: str, n_similar: int = 5) -> List[Dict]:
        """
        Находит похожие риски по семантической близости.
        
        Args:
            risk_id: ID исходного риска
            n_similar: Количество похожих рисков
            
        Returns:
            Список похожих рисков
        """
        # Получаем документ риска
        risk_data = self.get_risk_by_id(risk_id)
        if not risk_data:
            return []
        
        # Ищем похожие
        similar = self.risks.query(
            query_texts=[risk_data['document']],
            n_results=n_similar + 1,  # +1 чтобы исключить сам риск
            where={"risk_id": {"$ne": risk_id}}  # Исключаем сам риск
        )
        
        return self._format_results(similar)
    
    # ============ СТАТИСТИКА И АНАЛИТИКА ============
    
    def get_stats(self) -> Dict:
        """
        Возвращает статистику по базе данных.
        
        Returns:
            Словарь со статистикой
        """
        # Риски
        risks_data = self.risks.get(limit=1)
        risks_count = self.risks.count()
        
        # Нормы
        norms_data = self.norms.get(limit=1)
        norms_count = self.norms.count()
        
        # Связи
        connections_count = self.connections.count()
        
        # Категории рисков
        categories = self.get_all_categories()
        
        # Статьи ГК
        norms_all = self.norms.get()
        article_numbers = []
        for metadata in norms_all.get('metadatas', []):
            if 'article_number' in metadata:
                article_numbers.append(metadata['article_number'])
        
        # Подсчет уникальных статей
        unique_articles = len(set(article_numbers))
        
        return {
            "total_risks": risks_count,
            "total_norms": norms_count,
            "total_connections": connections_count,
            "risk_categories": len(categories),
            "unique_articles": unique_articles,
            "article_range": {
                "min": min(article_numbers, key=lambda x: int(x)) if article_numbers else None,
                "max": max(article_numbers, key=lambda x: int(x)) if article_numbers else None
            } if article_numbers else {}
        }
    
    def get_risk_distribution(self) -> Dict:
        """
        Распределение рисков по категориям и серьезности.
        
        Returns:
            Словарь с распределением
        """
        results = self.risks.get()
        
        by_category = {}
        by_severity = {str(i): 0 for i in range(1, 11)}
        
        for metadata in results.get('metadatas', []):
            # По категориям
            category = metadata.get('category', 'Неизвестно')
            by_category[category] = by_category.get(category, 0) + 1
            
            # По серьезности
            severity = str(metadata.get('severity', 0))
            if severity in by_severity:
                by_severity[severity] += 1
        
        return {
            "by_category": dict(sorted(by_category.items(), key=lambda x: x[1], reverse=True)),
            "by_severity": by_severity
        }
    
    # ============ СЛУЖЕБНЫЕ МЕТОДЫ ============
    
    def _create_risk_document(self, risk: Dict) -> str:
        """Создает текстовый документ для векторизации риска"""
        parts = [
            risk['header'],
            risk['metadata']['risk_title'],
            risk['metadata']['description'],
            risk['metadata']['pattern'],
            risk['metadata']['recommendation'],
            " ".join(risk['metadata']['consequences']),
            " ".join(risk['metadata']['relevant_articles']),
            risk['metadata']['risk_category'],
            risk['metadata']['document_type']
        ]
        return " ".join([str(p) for p in parts if p])
    
    def _create_norm_document(self, norm: Dict) -> str:
        """Создает текстовый документ для векторизации нормы"""
        parts = [
            f"Статья {norm['metadata']['article']} Гражданского кодекса РФ",
            norm['header'],
            norm['text'],
            " ".join(norm['metadata']['keywords'])
        ]
        return " ".join([str(p) for p in parts if p])
    
    def _build_where_clause(self, filters: Dict) -> Dict:
        """Строит условие WHERE для запросов"""
        if not filters:
            return None
        
        where = {}
        
        for key, value in filters.items():
            if key == 'severity_min':
                if 'severity' not in where:
                    where['severity'] = {}
                where['severity']['$gte'] = value
            elif key == 'severity_max':
                if 'severity' not in where:
                    where['severity'] = {}
                where['severity']['$lte'] = value
            elif key == 'category':
                where['category'] = value
            elif key == 'document_type':
                where['source_doc'] = value
            elif key == 'article_number':
                where['article_number'] = value
        
        return where if where else None
    
    def _format_results(self, results: Dict) -> List[Dict]:
        """Форматирует результаты запроса"""
        formatted = []
        
        if not results or 'ids' not in results:
            return formatted
        
        for i in range(len(results['ids'])):
            formatted.append({
                'id': results['ids'][i],
                'metadata': results['metadatas'][i] if results['metadatas'] else {},
                'document': results['documents'][i] if results['documents'] else "",
                'distance': results['distances'][i] if 'distances' in results else None
            })
        
        return formatted
    
    def _extract_article_number(self, norm_id: str) -> str:
        """Извлекает номер статьи из ID нормы"""
        # Форматы: "gk_123", "norm_456", etc.
        match = re.search(r'(\d+)', norm_id)
        return match.group(1) if match else norm_id
    
    def clear_database(self):
        """Очищает все данные в базе (только для тестирования!)"""
        self.client.reset()
        self._initialize_collections()