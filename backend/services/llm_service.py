import asyncio
import json
import os
from openai import AsyncOpenAI
from typing import Dict, List, Optional
import sys
from pathlib import Path

vector_db_path = Path(__file__).parent.parent.parent / "data"
if str(vector_db_path) not in sys.path:
    sys.path.insert(0, str(vector_db_path))
from vector_db import ContractRiskDB

_client: Optional[AsyncOpenAI] = None


def get_openai_client() -> AsyncOpenAI:
    global _client
    if _client is not None:
        return _client

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Не задан OPENAI_API_KEY. Добавьте ключ в переменные окружения.")

    _client = AsyncOpenAI(api_key=api_key)
    return _client

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


async def retrieve_rag_context(db: ContractRiskDB, text: str, n_results: int = 5) -> Dict[str, List[Dict]]:
    """Асинхронный поиск контекста (если ваша БД поддерживает asyncio)."""
    try:
        risks = await asyncio.to_thread(db.search_risks, query=text, n_results=n_results)
        norms = await asyncio.to_thread(db.search_norms, query=text, n_results=n_results)
        return {"risks": risks, "norms": norms}
    except Exception as e:
        print(f"[WARN] Ошибка при поиске в RAG: {e}")
        return {"risks": [], "norms": []}


def format_rag_context(rag_context: Dict[str, List[Dict]]) -> str:
    """Форматирует найденные риски и нормы для вставки в промпт (с полным выводом)."""
    context_str = ""

    if rag_context['risks']:
        context_str += "═══════ ИЗВЕСТНЫЕ РИСКИ ИЗ БД (ПОЛНЫЙ СПИСОК) ═══════\n\n"
        for i, risk in enumerate(rag_context['risks'], 1):
            header = risk.get('header', 'Без заголовка')
            text = risk.get('text', '')
            metadata = risk.get('metadata', {})
            severity = metadata.get('severity', 'не указана')
            recommendation = metadata.get('recommendation', '')
            risk_category = metadata.get('risk_category', 'общий')
            
            context_str += f"РИСК #{i}\n"
            context_str += f"  Заголовок: {header}\n"
            context_str += f"  Категория: {risk_category}\n"
            context_str += f"  Серьёзность: {severity}/10\n"
            context_str += f"  Текст:\n    {text}\n"
            if recommendation:
                context_str += f"  Рекомендация:\n    {recommendation}\n"
            context_str += "\n" + "-"*60 + "\n\n"
    else:
        context_str += "═══════ РИСКИ НЕ НАЙДЕНЫ ═══════\n\n"

    if rag_context['norms']:
        context_str += "═══════ РЕЛЕВАНТНЫЕ ЮРИДИЧЕСКИЕ НОРМЫ (ПОЛНЫЙ СПИСОК) ═══════\n\n"
        for i, norm in enumerate(rag_context['norms'], 1):
            header = norm.get('header', 'Без заголовка')
            text = norm.get('text', '')
            article = norm.get('metadata', {}).get('article', 'не указан')
            context_str += f"НОРМА #{i}\n"
            context_str += f"  Статья: {article}\n"
            context_str += f"  Заголовок: {header}\n"
            context_str += f"  Текст:\n    {text}\n"
            context_str += "\n" + "-"*60 + "\n\n"
    else:
        context_str += "═══════ НОРМЫ НЕ НАЙДЕНЫ ═══════\n\n"

    return context_str


async def analyze_document(text: str, db: Optional[ContractRiskDB] = None) -> str:
    """
    Анализирует текст договора с использованием RAG и OpenAI.
    Полный дебаг: вывод всех данных, промптов и контекста.
    """
    if not text or len(text) < 30:
        raise ValueError("Текст договора слишком короткий (минимум 30 символов)")

    if db is None:
        default_db_path = Path(__file__).resolve().parents[2] / "data" / "chroma_db"
        db = ContractRiskDB(persist_directory=str(default_db_path))

    print("[DEBUG] Сбор RAG-контекста из векторной БД")
    
    # 1. Извлекаем RAG-контекст
    rag_context = await retrieve_rag_context(db, text)
    
    print("\n[DEBUG] Найдено в БД:")
    print(f"   → Рисков: {len(rag_context['risks'])}")
    print(f"   → Норм: {len(rag_context['norms'])}")
    
    if not rag_context['risks'] and not rag_context['norms']:
        print("[WARN] RAG-контекст пуст. Проверьте:")
        print("    - Существует ли ./chroma_db?")
        print("    - Есть ли данные в коллекциях 'risks' и 'norms'?")
        print("    - Совпадает ли текст договора с семантикой записей в БД?")

    # 2. Формируем контекст
    rag_context_str = format_rag_context(rag_context)
    
    print("\n[DEBUG] Полный RAG-контекст (отправится в prompt):")
    print("="*80)
    print(rag_context_str)
    print("="*80)

    # 3. Формируем system_prompt
    system_prompt = (
        "Ты юридический ассистент. Тебе передан текст гражданско-правового договора. "
        "Твоя задача — строго по заданной схеме SGR проанализировать договор и вернуть "
        "СТРОГО валидный JSON без комментариев и дополнительного текста.\n\n"
        
        "ДЛЯ СПРАВКИ — ИЗВЕСТНЫЕ РИСКИ И НОРМЫ ИЗ БАЗЫ ДАННЫХ:\n"
        f"{rag_context_str}\n\n"
        
        "ИСПОЛЬЗУЙ ЭТУ ИНФОРМАЦИЮ ОБЯЗАТЕЛЬНО:\n"
        "- Если в договоре есть элементы, совпадающие с рисками выше — укажи их в 'issues'.\n"
        "- В 'recommendation' приводи рекомендации из раздела 'Рекомендация' для каждого риска.\n"
        "- Ссылайся на юридические нормы в 'law_references'.\n\n"
        
        "Схема SGR (образец ключей и ожидаемого смысла значений):\n"
        f"{json.dumps(SGR_SCHEMA, ensure_ascii=False, indent=2)}\n\n"
        
        "Требования:\n"
        "1) Соблюдай ВСЕ ключи и структуру словаря.\n"
        "2) Заполняй поля на основе текста договора. Если информации нет — пиши 'не указано'.\n"
        "3) Оценивай риск на основе как текста договора, так и рисков из БД.\n"
        "4) В 'summary.critical_issues' перечисли все найденные риски из БД, если они применимы.\n"
        "5) Верни ТОЛЬКО JSON-объект, без обёрток, без Markdown, без комментариев."
    )

    user_prompt = f'""" {text} """'

    print("\n[DEBUG] Полный system prompt:")
    print("="*80)
    print(system_prompt)
    print("="*80)

    # 4. Вызываем OpenAI
    print("\n[DEBUG] Отправка запроса в OpenAI...")
    client = get_openai_client()
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
        )
        raw = response.choices[0].message.content
        print("\n[DEBUG] Получен ответ от LLM:")
        print("-" * 80)
        print(raw)
        print("-" * 80)
    except Exception as e:
        print(f"\n[ERROR] Ошибка OpenAI: {e}")
        raise

    # 5. Парсим JSON
    try:
        parsed = json.loads(raw)
        result = json.dumps(parsed, ensure_ascii=False, indent=2)
        print("\n[DEBUG] Ответ успешно распарсен как JSON")
        return result
    except json.JSONDecodeError as e:
        print(f"\n[WARN] JSON-парсинг не удался: {e}")
        print("Возвращаем сырой ответ.")
        return raw
    



# ==================== ТЕСТОВЫЙ ЗАПУСК ====================
if __name__ == "__main__":
    async def _test():
        # Инициализация векторной БД (укажите правильный путь, если отличается)
        db = ContractRiskDB(persist_directory="./chroma_db")
        
        # Пример договора
        sample_contract = """
        ДОГОВОР ПОСТАВКИ № 42
        от 10.06.2024 г.

        Стороны:
        Поставщик: ООО "ТехноПоставка", ИНН 7712345678
        Покупатель: АО "СтройГрупп", ИНН 7890123456

        1. Предмет договора: Поставка строительных материалов (цемент, арматура).
        2. Цена: 1 200 000 рублей с НДС. Оплата в течение 10 рабочих дней с момента поставки.
        3. Срок поставки: не позднее 25.06.2024.
        4. Гарантия: 6 месяцев.
        5. Ответственность: неустойка 0.1% в день просрочки.
        """

        try:
            result = await analyze_document(sample_contract, db)
            print("\n" + "="*70)
            print("РЕЗУЛЬТАТ АНАЛИЗА (RAG + OpenAI):")
            print("="*70)
            print(result)

            # Сохраняем в файл
            with open("test_analysis_result.json", "w", encoding="utf-8") as f:
                f.write(result)
            print("\nРезультат сохранён в test_analysis_result.json")

        except Exception as e:
            print(f"\nОшибка при анализе: {e}")
            import traceback
            traceback.print_exc()

    # Запуск асинхронной функции
    asyncio.run(_test())
