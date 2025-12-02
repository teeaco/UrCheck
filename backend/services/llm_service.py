import asyncio
import json
from openai import AsyncOpenAI

client = AsyncOpenAI(api_key = "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")  # API-ключ должен быть в переменной окружения OPENAI_API_KEY


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


async def analyze_document(text: str) -> str:
    """
    Анализирует текст договора с помощью LLM и возвращает JSON-строку
    по SGR-схеме (как в SGR_SCHEMA).
    """
    system_prompt = (
        "Ты юридический ассистент. Тебе передан текст гражданско-правового договора. "
        "Твоя задача — строго по заданной схеме SGR проанализировать договор и вернуть "
        "СТРОГО валидный JSON без комментариев и дополнительного текста.\n\n"
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
        f'""" {text} """'
    )

    response = await client.chat.completions.create(
        model="gpt-4o-mini",  # поставь свою модель
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.2,
    )

    raw = response.choices[0].message.content

    # На всякий случай можно проверить, что это валидный JSON и отформатировать
    try:
        parsed = json.loads(raw)
        result = json.dumps(parsed, ensure_ascii=False, indent=2)
    except json.JSONDecodeError:
        # Если LLM чуть ошибся в формате — можно либо кинуть ошибку,
        # либо попытаться почистить через дополнительный промпт/регексп.
        # Здесь просто пробрасываем как есть.
        result = raw

    return result