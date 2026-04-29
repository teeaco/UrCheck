# vector_db.py
import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import re

class ContractRiskDB:
    """
    Векторная база данных для хранения рисков, норм ГК и связей между ними.
    Все методы возвращают данные в единообразном формате:
    {
        'id': str,
        'header': str,
        'text': str,
        'metadata': dict
    }
    """
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(anonymized_telemetry=False, allow_reset=True)
        )
        self._initialize_collections()
    
    def _initialize_collections(self):
        self.risks = self.client.get_or_create_collection(name="risks")
        self.norms = self.client.get_or_create_collection(name="norms")
        self.connections = self.client.get_or_create_collection(name="connections")
    
    # ============ РИСКИ ============
    
    def add_risks(self, risks: List[Dict]) -> int:
        ids = []
        documents = []
        metadatas = []
        
        for risk in risks:
            doc_text = self._create_risk_document(risk)
            risk_id = risk['id']
            
            # Сохраняем header и text в метаданные для прямого доступа
            metadata = {
                "type": "risk",
                "id": risk_id,
                "header": risk.get('header', ''),
                "text": risk.get('text', ''),
                "risk_title": risk['metadata'].get('risk_title', ''),
                "risk_category": risk['metadata'].get('risk_category', ''),
                "severity": int(risk['metadata'].get('severity', 5)),
                "document_type": risk['metadata'].get('document_type', ''),
                "source_file": risk['metadata'].get('source_file', ''),
                # Преобразуем списки в строки
                "relevant_articles": "|".join(risk['metadata'].get('relevant_articles', [])),
                "consequences": "|".join(risk['metadata'].get('consequences', [])),
                "recommendation": risk['metadata'].get('recommendation', ''),
                "description": risk['metadata'].get('description', '')
            }
                        
            ids.append(risk_id)
            documents.append(doc_text)
            metadatas.append(metadata)
        
        self.risks.add(ids=ids, documents=documents, metadatas=metadatas)
        return len(risks)
    
    def search_risks(self, query: str, n_results: int = 10, **filters) -> List[Dict]:
        where_clause = self._build_where_clause(filters)
        results = self.risks.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause
        )
        return self._format_query_results(results)
    
    def get_risk_by_id(self, risk_id: str) -> Optional[Dict]:
        try:
            result = self.risks.get(ids=[risk_id])
            if result['ids']:
                meta = result['metadatas'][0] if result['metadatas'] else {}
                doc = result['documents'][0] if result['documents'] else ""
                
                # Восстанавливаем списки из строк
                restored_meta = meta.copy()
                if 'relevant_articles' in restored_meta and isinstance(restored_meta['relevant_articles'], str):
                    restored_meta['relevant_articles'] = restored_meta['relevant_articles'].split('|') if restored_meta['relevant_articles'] else []
                if 'consequences' in restored_meta and isinstance(restored_meta['consequences'], str):
                    restored_meta['consequences'] = restored_meta['consequences'].split('|') if restored_meta['consequences'] else []
                if 'keywords' in restored_meta and isinstance(restored_meta['keywords'], str):
                    restored_meta['keywords'] = restored_meta['keywords'].split('|') if restored_meta['keywords'] else []
                
                return {
                    'id': result['ids'][0],
                    'header': meta.get('header', meta.get('risk_title', 'Без заголовка')),
                    'text': meta.get('text', doc),
                    'metadata': restored_meta
                }
        except Exception:
            pass
        return None
    
    def get_risks_for_norm(self, norm_id: str) -> List[Dict]:
        """Получает все риски, связанные с нормой."""
        results = self.connections.get(
            where={
                "$and": [
                    {"norm_id": norm_id},
                    {"direction": "norm_to_risk"}
                ]
            }
        )
        risk_ids = [meta['risk_id'] for meta in (results.get('metadatas') or [])]
        if not risk_ids:
            return []
        
        risk_data = self.risks.get(ids=risk_ids)
        return self._format_get_results(risk_data)
    
    # ============ НОРМЫ ============
    
    def add_norms(self, norms: List[Dict]) -> int:
        ids = []
        documents = []
        metadatas = []
        
        for norm in norms:
            doc_text = self._create_norm_document(norm)
            norm_id = norm['id']
            
            metadata = {
                "type": "norm",
                "id": norm_id,
                "header": norm.get('header', ''),
                "text": norm.get('text', ''),
                "article": norm['metadata'].get('article', ''),
                # Преобразуем список ключевых слов в строку
                "keywords": "|".join(norm['metadata'].get('keywords', [])),
                "law_type": norm['metadata'].get('law_type', 'ГК РФ')
            }
                        
            ids.append(norm_id)
            documents.append(doc_text)
            metadatas.append(metadata)
        
        self.norms.add(ids=ids, documents=documents, metadatas=metadatas)
        return len(norms)
    
    def search_norms(self, query: str, n_results: int = 10, **filters) -> List[Dict]:
        where_clause = self._build_where_clause(filters)
        results = self.norms.query(
            query_texts=[query],
            n_results=n_results,
            where=where_clause
        )
        return self._format_query_results(results)
    
    def get_norm_by_article(self, article_number: str) -> Optional[Dict]:
        results = self.norms.get(where={"article": article_number})
        if results['ids']:
            meta = results['metadatas'][0] if results['metadatas'] else {}
            doc = results['documents'][0] if results['documents'] else ""
            return {
                'id': results['ids'][0],
                'header': meta.get('header', f'Статья {article_number} ГК РФ'),
                'text': meta.get('text', doc),
                'metadata': meta
            }
        return None
    
    def get_norm_by_id(self, norm_id: str) -> Optional[Dict]:
        try:
            result = self.norms.get(ids=[norm_id])
            if result['ids']:
                meta = result['metadatas'][0] if result['metadatas'] else {}
                doc = result['documents'][0] if result['documents'] else ""
                return {
                    'id': result['ids'][0],
                    'header': meta.get('header', 'Без заголовка'),
                    'text': meta.get('text', doc),
                    'metadata': meta
                }
        except Exception:
            pass
        return None
    
    # ============ СВЯЗИ ============
    
    def add_connections(self, connections: Dict) -> int:
        ids = []
        documents = []
        metadatas = []
        count = 0
        
        for risk_id, norm_ids in connections.get('risk_to_norms', {}).items():
            for norm_id in norm_ids:
                article_num = self._extract_article_number(norm_id)
                conn_id = f"conn_{risk_id}_{norm_id}"
                doc = f"Риск {risk_id} связан со статьей {article_num} ГК РФ"
                ids.append(conn_id)
                documents.append(doc)
                metadatas.append({
                    "risk_id": risk_id,
                    "norm_id": norm_id,
                    "article_number": article_num,
                    "direction": "risk_to_norm"
                })
                count += 1
        
        for norm_id, risk_ids in connections.get('norm_to_risks', {}).items():
            for risk_id in risk_ids:
                article_num = self._extract_article_number(norm_id)
                conn_id = f"conn_{risk_id}_{norm_id}_rev"
                doc = f"Статья {article_num} ГК РФ связана с риском {risk_id}"
                ids.append(conn_id)
                documents.append(doc)
                metadatas.append({
                    "risk_id": risk_id,
                    "norm_id": norm_id,
                    "article_number": article_num,
                    "direction": "norm_to_risk"
                })
                count += 1
        
        if ids:
            self.connections.add(ids=ids, documents=documents, metadatas=metadatas)
        return count
    
    # ============ СЛУЖЕБНЫЕ ============
    
    def _create_risk_document(self, risk: Dict) -> str:
        """Создает текстовый документ для векторизации риска. Фокус на сути: что не так и почему."""
        meta = risk.get('metadata', {})
        parts = [
            meta.get('risk_title', ''),
            meta.get('description', ''),
            meta.get('pattern', ''),          # ← Ключевое поле: проблемная формулировка
            " ".join(meta.get('consequences', []))
        ]
        return " ".join([str(p) for p in parts if p])
    
    def _create_norm_document(self, norm: Dict) -> str:
        meta = norm.get('metadata', {})
        parts = [
            f"Статья {meta.get('article', '')} ГК РФ: {norm.get('header', '')}",
            norm.get('text', ''),
            " ".join(meta.get('keywords', []))
        ]
        return " ".join([str(p) for p in parts if p])
    
    def _extract_article_number(self, norm_id: str) -> str:
        match = re.search(r'(\d+)', norm_id)
        return match.group(1) if match else norm_id
    
    def _build_where_clause(self, filters: Dict) -> Optional[Dict]:
        if not filters:
            return None
        where = {}
        for key, value in filters.items():
            # Пропускаем None-значения
            if value is None:
                continue
                
            if key == 'severity_min':
                if 'severity' not in where:
                    where['severity'] = {}
                where['severity']['$gte'] = value
            elif key == 'severity_max':
                if 'severity' not in where:
                    where['severity'] = {}
                where['severity']['$lte'] = value
            elif key == 'category':
                where['risk_category'] = value
            elif key == 'document_type':
                where['document_type'] = value
            elif key == 'article':
                where['article'] = value
        
        return where if where else None
    
    def _format_query_results(self, results) -> List[Dict]:
        if not results or not results.get('ids') or len(results['ids'][0]) == 0:
            return []
        
        formatted = []
        ids = results['ids'][0]
        metadatas = results['metadatas'][0] if results.get('metadatas') else [{}] * len(ids)
        documents = results['documents'][0] if results.get('documents') else [""] * len(ids)
        distances = results['distances'][0] if results.get('distances') else [None] * len(ids)
        
        for i in range(len(ids)):
            meta = metadatas[i] or {}
            doc = documents[i] or ""
            
            # Восстанавливаем списки
            restored_meta = meta.copy()
            for key in ['relevant_articles', 'consequences', 'keywords']:
                if key in restored_meta and isinstance(restored_meta[key], str):
                    restored_meta[key] = restored_meta[key].split('|') if restored_meta[key] else []
            
            formatted.append({
                'id': ids[i],
                'header': meta.get('header', meta.get('risk_title', 'Без заголовка')),
                'text': meta.get('text', doc),
                'metadata': restored_meta,
                'distance': distances[i]
            })
        return formatted
        
    def _format_get_results(self, results) -> List[Dict]:
        """Форматирует результаты collection.get() — плоская структура."""
        if not results or not results.get('ids'):
            return []
        
        formatted = []
        ids = results['ids']
        metadatas = results.get('metadatas') or [{}] * len(ids)
        documents = results.get('documents') or [""] * len(ids)
        
        for i in range(len(ids)):
            meta = metadatas[i] or {}
            doc = documents[i] or ""
            
            # Восстанавливаем списки из строк
            restored_meta = meta.copy()
            list_fields = ['relevant_articles', 'consequences', 'keywords']
            for field in list_fields:
                if field in restored_meta:
                    value = restored_meta[field]
                    if isinstance(value, str):
                        restored_meta[field] = value.split('|') if value else []
                    elif not isinstance(value, list):
                        restored_meta[field] = []
            
            formatted.append({
                'id': ids[i],
                'header': meta.get('header', meta.get('risk_title', 'Без заголовка')),
                'text': meta.get('text', doc),
                'metadata': restored_meta
            })
        return formatted
    
    def get_stats(self) -> Dict:
        norms_all = self.norms.get()
        articles = [m.get('article') for m in (norms_all.get('metadatas') or []) if m.get('article')]
        unique_articles = len(set(articles)) if articles else 0
        
        risk_cats = set()
        risks_all = self.risks.get()
        for m in (risks_all.get('metadatas') or []):
            if 'risk_category' in m:
                risk_cats.add(m['risk_category'])
        
        return {
            "total_norms": self.norms.count(),
            "total_risks": self.risks.count(),
            "total_connections": self.connections.count(),
            "unique_articles": unique_articles,
            "risk_categories": len(risk_cats)
        }
    
    def clear_database(self):
        self.client.reset()
        self._initialize_collections()