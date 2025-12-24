"""
RAG-интегрированный анализ договоров с использованием векторной БД и OpenAI.

Классический паттерн RAG:
1. Получить текст договора
2. Поискать релевантные риски и нормы в векторной БД
3. Подставить контекст (RAG context) в системный промпт
4. Отправить расширенный запрос в GPT
5. Получить структурированный JSON по SGR-схеме
"""

import asyncio
import json
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from openai import AsyncOpenAI

vector_db_path = Path(__file__).parent.parent.parent / "data"
if str(vector_db_path) not in sys.path:
    sys.path.insert(0, str(vector_db_path))

from vector_db import ContractRiskDB

# ==================== SGR SCHEMA ====================
SGR_SCHEMA = {
  "case_info": {
    "contract_type": "тип договора",
    "parties": {
      "party_a": "наименование первой стороны",
      "party_b": "наименование второй стороны"
    },
    "signing_date": "дата заключения или 'не указана'"
  },
  "section_1_subject": {
    "criterion": "Предмет договора",
    "status": "найден/не найден",
    "content": "точное описание",
    "risk_level": "низкий/средний/высокий",
    "issues": [],
    "recommendation": "рекомендация"
  },
  "section_2_price_payment": {
    "criterion": "Цена и порядок оплаты",
    "status": "найден/не найден",
    "total_price": "указана ли цена",
    "payment_term": "срок оплаты",
    "advance_payment": {
      "present": "да/нет",
      "percentage": "если да, сколько %"
    },
    "tax_obligation": {
      "vat_mentioned": "да/нет",
      "who_pays": "кто платит НДС"
    },
    "risk_level": "низкий/средний/высокий",
    "issues": [],
    "recommendation": "рекомендация"
  },
  "section_3_execution_deadline": {
    "criterion": "Срок исполнения договора",
    "status": "найден/не найден",
    "deadline": "указанный срок",
    "unit": "дни/рабочие дни/календарные дни",
    "delivery_place": "место поставки указано?",
    "risk_level": "низкий/средний/высокий",
    "issues": [],
    "recommendation": "рекомендация"
  },
  "section_4_acceptance_term": {
    "criterion": "Срок приёмки работ, товара, услуг",
    "status": "найден/не найден",
    "acceptance_period": "указанный период",
    "procedures": "процедура приёмки описана?",
    "risk_level": "низкий/средний/высокий",
    "issues": [],
    "recommendation": "рекомендация"
  },
  "section_5_contract_validity": {
    "criterion": "Срок действия договора",
    "status": "найден/не найден",
    "start_date": "дата начала",
    "end_date": "дата окончания",
    "obligation_termination_date": "дата прекращения обязательств",
    "risk_level": "низкий/средний/высокий",
    "issues": [],
    "recommendation": "рекомендация"
  },
  "section_6_warranty_period": {
    "criterion": "Гарантийный срок",
    "status": "найден/не найден",
    "warranty_period": "указанный период",
    "obligations": "обязанности при дефектах",
    "who_is_responsible": "ответственная сторона",
    "risk_level": "низкий/средний/высокий",
    "issues": [],
    "recommendation": "рекомендация"
  },
  "section_7_liability": {
    "criterion": "Ответственность сторон",
    "status": "найден/не найден",
    "penalties_for_delay": "штрафы за просрочку",
    "penalties_for_quality": "штрафы за некачество",
    "penalty_balance": "сбалансированы?",
    "limitation_clause": "ограничение ответственности?",
    "risk_level": "низкий/средний/высокий",
    "issues": [],
    "recommendation": "рекомендация"
  },
  "section_8_jurisdiction": {
    "criterion": "Подсудность",
    "status": "найден/не найден",
    "jurisdiction": "указанный суд",
    "is_favorable": "выгодна для обеих сторон?",
    "risk_level": "низкий/средний/высокий",
    "issues": [],
    "recommendation": "рекомендация"
  },
  "section_9_requisites": {
    "criterion": "Реквизиты сторон",
    "status": "найден/не найден",
    "party_a_details": {
      "name": "наименование",
      "address": "адрес",
      "bank_details": "есть ли реквизиты"
    },
    "party_b_details": {
      "name": "наименование",
      "address": "адрес",
      "bank_details": "есть ли реквизиты"
    },
    "completeness": "полные ли реквизиты",
    "risk_level": "низкий/средний/высокий",
    "issues": [],
    "recommendation": "рекомендация"
  },
  "summary": {
    "overall_assessment": "БЕЗОПАСНЫЙ / ТРЕБУЕТ ДОРАБОТКИ / РИСКОВАННЫЙ",
    "critical_issues": [],
    "medium_issues": [],
    "low_issues": [],
    "total_risk_score": "число от 1 до 10",
    "priority_actions": [],
    "law_references": []
  },
  "judge_questions": [],
  "next_steps": []
}


class RAGAnalyzer:
    """
    Анализатор договоров с поддержкой RAG.
    Использует векторную БД для поиска релевантных контекстов перед LLM.
    """
    
    def __init__(
        self,
        api_key: str,
        db: ContractRiskDB,
        model: str = "gpt-4o-mini",
        max_context_items: int = 5
    ):
        """
        Args:
            api_key: OpenAI API ключ
            db: Инициализированный экземпляр ContractRiskDB
            model: Модель OpenAI (gpt-4, gpt-4o-mini и т.д.)
            max_context_items: Максимальное количество релевантных рисков/норм для контекста
        """
        self.client = AsyncOpenAI(api_key=api_key)
        self.db = db
        self.model = model
        self.max_context_items = max_context_items
    
    async def _retrieve_rag_context(self, text: str) -> Dict[str, List[Dict]]:
        """
        Извлекает релевантные риски и нормы из векторной БД.
        
        Returns:
            {
                'risks': [...],      # релевантные риски
                'norms': [...]       # релевантные нормы
            }
        """
        try:
            # Поиск рисков по тексту договора
            risks = self.db.search_risks(
                query=text,
                n_results=self.max_context_items
            )
            
            # Поиск норм по тексту договора
            norms = self.db.search_norms(
                query=text,
                n_results=self.max_context_items
            )
            
            return {
                'risks': risks,
                'norms': norms
            }
        except Exception as e:
            print(f"⚠️  Ошибка при поиске в RAG: {e}")
            return {'risks': [], 'norms': []}
    
    def _format_rag_context(self, rag_context: Dict[str, List[Dict]]) -> str:
        """Форматирует контекст RAG в удобный для промпта вид."""
        context_str = ""
        
        if rag_context['risks']:
            context_str += "═══════ ИЗВЕСТНЫЕ РИСКИ ИЗ БД ═══════\n\n"
            for i, risk in enumerate(rag_context['risks'][:self.max_context_items], 1):
                header = risk.get('header', 'Без заголовка')
                text = risk.get('text', '')[:300]  # обрезаем для компактности
                severity = risk.get('metadata', {}).get('severity', 'не указана')
                recommendation = risk.get('metadata', {}).get('recommendation', '')
                
                context_str += f"{i}. {header}\n"
                context_str += f"   Тип: {risk.get('metadata', {}).get('risk_category', 'общий')}\n"
                context_str += f"   Серьёзность: {severity}/10\n"
                context_str += f"   Описание: {text}...\n"
                if recommendation:
                    context_str += f"   Рекомендация: {recommendation}\n"
                context_str += "\n"
        
        if rag_context['norms']:
            context_str += "═══════ РЕЛЕВАНТНЫЕ ЮРИДИЧЕСКИЕ НОРМЫ ═══════\n\n"
            for i, norm in enumerate(rag_context['norms'][:self.max_context_items], 1):
                header = norm.get('header', 'Без заголовка')
                text = norm.get('text', '')[:300]
                article = norm.get('metadata', {}).get('article', '')
                
                context_str += f"{i}. {header}"
                if article:
                    context_str += f" ({article})"
                context_str += "\n"
                context_str += f"   {text}...\n\n"
        
        return context_str
    
    async def analyze_document(self, text: str) -> str:
        """
        Анализирует текст договора с использованием RAG.
        
        Args:
            text: Текст договора
            
        Returns:
            JSON-строка с результатами анализа по SGR-схеме
        """
        if not text or len(text) < 30:
            raise ValueError("Текст договора слишком короткий (минимум 30 символов)")
        
        # Шаг 1: Извлекаем релевантный контекст из БД
        print("🔍 Поиск релевантных рисков и норм в БД...")
        rag_context = await self._retrieve_rag_context(text)
        rag_context_str = self._format_rag_context(rag_context)
        
        print(f"✅ Найдено рисков: {len(rag_context['risks'])}, норм: {len(rag_context['norms'])}")
        
        # Шаг 2: Собираем системный промпт с контекстом RAG
        system_prompt = (
            "Ты юридический ассистент специализирующийся на анализе гражданско-правовых договоров. "
            "Твоя задача — строго по заданной схеме SGR проанализировать договор и вернуть "
            "СТРОГО валидный JSON без комментариев и дополнительного текста.\n\n"
            
            "ДЛЯ СПРАВКИ — ИЗВЕСТНЫЕ РИСКИ И НОРМЫ ИЗ БАЗЫ ДАННЫХ:\n"
            f"{rag_context_str}\n\n"
            
            "Используй эту информацию в качестве контекста и справочного материала при анализе. "
            "Если договор содержит элементы, похожие на риски из БД, упомяни их в разделе issues и recommendation.\n\n"
            
            "Схема SGR (образец ключей и ожидаемого смысла значений):\n"
            f"{json.dumps(SGR_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
            
            "Требования:\n"
            "1) Соблюдай все ключи и структуру словаря.\n"
            "2) Заполняй поля на основе текста договора. Если информации нет — пиши 'не указано' или оставляй массив [] пустым.\n"
            "3) Оцени риск (низкий/средний/высокий) осознанно, поясняя проблемы в issues и рекомендации.\n"
            "4) Верни ТОЛЬКО JSON-объект, без обёрток, без Markdown, без комментариев."
        )
        
        user_prompt = (
            "Текст договора ниже между тройными кавычками. Проанализируй его и заполни SGR-схему.\n\n"
            f'"""\n{text}\n"""'
        )
        
        # Шаг 3: Отправляем в LLM с контекстом RAG
        print("🤖 Отправляю запрос в OpenAI...")
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,  # Низкая температура для консистентности JSON
        )
        
        raw = response.choices[0].message.content
        
        # Шаг 4: Парсим и форматируем результат
        try:
            parsed = json.loads(raw)
            result = json.dumps(parsed, ensure_ascii=False, indent=2)
            print("✅ Анализ успешно завершён")
        except json.JSONDecodeError as e:
            print(f"⚠️  LLM вернул невалидный JSON: {e}")
            result = raw
        
        return result


async def main():
    """Пример использования RAG анализатора."""
    
    # Инициализация БД
    db = ContractRiskDB(persist_directory="./chroma_db")
    
    # Инициализация анализатора с RAG
    analyzer = RAGAnalyzer(
        api_key="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",
        db=db,
        model="gpt-4o-mini",
        max_context_items=5
    )
    
    # Пример договора
    sample_contract = """
    ДОГОВОР ПОСТАВКИ
    
    Дата: 15 декабря 2024 г.
    
    Стороны:
    - ООО "Поставщик" (далее Поставщик)
    - ЗАО "Покупатель" (далее Покупатель)
    
    Предмет договора:
    Поставщик обязуется поставить Покупателю материалы в количестве 1000 шт.
    
    Цена и оплата:
    Цена за единицу: 500 рублей.
    Общая стоимость: 500 000 рублей.
    Оплата производится в течение 30 дней с момента получения счета.
    Авансовый платеж: 20%.
    
    Сроки поставки:
    Поставка должна быть осуществлена не позднее 45 дней с момента подписания договора.
    Место поставки: склад Покупателя по адресу...
    
    Ответственность:
    За просрочку поставки Поставщик выплачивает неустойку в размере 0,5% от суммы договора в день просрочки.
    Максимум неустойки: 10% от суммы договора.
    
    Гарантия: 12 месяцев с момента поставки.
    """
    
    # Анализ
    result = await analyzer.analyze_document(sample_contract)
    
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТ АНАЛИЗА:")
    print("="*60)
    print(result)
    
    # Сохранение результата в файл
    with open("analysis_result.json", "w", encoding="utf-8") as f:
        f.write(result)
    print("\n✅ Результат сохранён в analysis_result.json")


if __name__ == "__main__":
    asyncio.run(main())