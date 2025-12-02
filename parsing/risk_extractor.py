# llm_extractor_fixed.py
import json
import re
from typing import List, Dict, Optional
from docx import Document

class StrictRuleBasedExtractor:
    def extract_risks(self, filepath: str) -> List[Dict]:
        print(f"Читаю файл: {filepath}")
        
        try:
            doc = Document(filepath)
        except Exception as e:
            print(f"Ошибка чтения DOCX: {e}")
            return []
        
        # весь
        all_paragraphs = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                all_paragraphs.append(text)
        risks = []
        
        for i in range(len(all_paragraphs)):
            text = all_paragraphs[i]
            if self.is_concrete_subrisk(text):
                print(f"!!! Найден подриск: {text[:60]}...")
                
                header = text
                content_parts = []
                
                # содержание до следующего подриска
                j = i + 1
                while j < len(all_paragraphs):
                    next_text = all_paragraphs[j]
                    
                    if self.is_concrete_subrisk(next_text):
                        break
                    
                    # заголовок НАХУЙ
                    if self.is_general_header(next_text):
                        break
                    
                    content_parts.append(next_text)
                    j += 1
                
                content = ' '.join(content_parts)
                
                # риск только при наличии содержания
                if content.strip() and len(content) > 30:
                    risk = self.create_risk(header, content, len(risks))
                    risks.append(risk)
        
        print(f"Найдено {len(risks)} конкретных подрисков")
        return risks
    
    def is_concrete_subrisk(self, text: str) -> bool:
        # цифра.цифра. пробел
        pattern = r'^\d+\.\d+\.\s+'
        
        # Дополнительная проверка
        if re.match(pattern, text):
            # не оглавление
            if 'Оглавление' in text or 'оглавление' in text:
                return False
            
            # слово там где надо
            text_without_number = re.sub(r'^\d+\.\d+\.\s+', '', text)
            if 'риск' in text_without_number.lower():
                return True
        
        return False
    
    def is_general_header(self, text: str): #нахуй сразу
        patterns = [
            r'^\d+\.\s+[А-Я]',  # 1. Риски заказчика...
            r'^Риски заказчика при',  # Риски заказчика при...
            r'^Рассмотрим основные',
            r'^Оглавление',
            r'^При заключении договора'
        ]
        
        return any(re.search(p, text, re.IGNORECASE) for p in patterns)
    
    def create_risk(self, header: str, text: str, idx: int): #струткурирование
        
        # статьи ГК РФ
        articles = re.findall(r'ст\.\s*\d+', text)
        
        # извлекаем ключевые последствия
        consequences = self.extract_consequences(text)
        
        # серьезность
        severity = self.estimate_severity(text)
        
        # категория
        category = self.determine_category(header)
        
        # название риска (без нумерации)
        risk_title = re.sub(r'^\d+\.\d+\.\s+', '', header)
        
        # описание
        description = self.create_description(text)
        
        # рекомендацию
        recommendation = self.extract_recommendation(text)
        
        # паттерн
        pattern = self.extract_pattern(header)
        
        return {
            "id": f"risk_{idx}",
            "type": "risk",
            "header": header,
            "body": text[:300] + "..." if len(text) > 300 else text,
            "metadata": {
                "risk_title": risk_title,
                "description": description,
                "pattern": pattern,
                "recommendation": recommendation,
                "severity": severity,
                "consequences": consequences,
                "relevant_articles": list(set(articles)),  # убираем дубли
                "risk_category": category,
                "source": "КонсультантПлюс, 2025",
                "extraction_method": "Strict Rule-based"
            }
        }
    
    def create_description(self, text: str) -> str:
        # разделяем на предложения
        sentences = re.split(r'[.!?]\s+', text)
        for sentence in sentences:
            # поиск по слову
            if any(keyword in sentence.lower() for keyword in [
                'риск заключается', 'опасность состоит', 'проблема в том',
                'может привести', 'влечет', 'приводит к'
            ]):
                return sentence.strip()[:150]
        
        # если не нашли, берем первое предложение
        if sentences and len(sentences[0]) > 20:
            return sentences[0].strip()[:150]
        
        return "Риск связан с договорными условиями"
    
    def extract_consequences(self, text: str) -> List[str]:
        consequences = []
        text_lower = text.lower()
        
        # ключевые фразы и их описания
        consequence_map = {
            'договор может быть признан незаключенным': 'Договор признается незаключенным',
            'признан незаключенным': 'Признание договора незаключенным',
            'не сможете требовать': 'Потеря права требовать исполнения',
            'не вправе требовать': 'Потеря права требовать исполнения',
            'обязаны будете оплатить': 'Обязанность оплатить работы',
            'должны будете оплатить': 'Обязанность оплатить работы',
            'возместить убытки': 'Обязанность возместить убытки',
            'нести ответственность': 'Привлечение к ответственности',
            'не сможете отказаться': 'Потеря права отказаться',
            'лишаетесь права': 'Потеря права',
            'риск несогласования': 'Признание условия несогласованным',
            'не применяются': 'Условия не применяются'
        }
        
        for phrase, consequence in consequence_map.items():
            if phrase in text_lower:
                consequences.append(consequence)
        
        # убираем дубли и ограничиваем количество
        unique_consequences = []
        for c in consequences:
            if c not in unique_consequences:
                unique_consequences.append(c)
        
        if not unique_consequences:
            unique_consequences.append('Требуется анализ договорных условий')
        
        return unique_consequences[:3]
    
    def estimate_severity(self, text: str) -> int:
        """Оценивает серьезность риска"""
        text_lower = text.lower()
        
        # высокая серьезность (8-10)
        if any(phrase in text_lower for phrase in [
            'договор может быть признан незаключенным',
            'расторжение договора',
            'существенное нарушение',
            'признан незаключенным'
        ]):
            return 9
        
        # средняя серьезность (6-7)
        if any(phrase in text_lower for phrase in [
            'убытки',
            'взыскание',
            'ответственность',
            'штраф',
            'неустойка'
        ]):
            return 7
        
        # низкая серьезность (4-5)
        if any(phrase in text_lower for phrase in [
            'не сможете',
            'не вправе',
            'лишаетесь права',
            'не применяется'
        ]):
            return 5
        
        return 4
    
    def determine_category(self, header: str) -> str:
        header_lower = header.lower()
        
        # категории
        categories = [
            ('Предмет договора', ['предмет', 'характеристики', 'параметры', 'объем', 'результат']),
            ('Сроки выполнения', ['срок', 'время', 'период', 'начальн', 'конечн']),
            ('Качество работ', ['качество', 'гарантий', 'недостатки', 'устранен']),
            ('Цена и оплата', ['цена', 'оплата', 'стоимость', 'платеж']),
            ('Приемка работ', ['приемка', 'акт', 'проверка', 'извещен']),
            ('Имущество и материалы', ['имущество', 'материал', 'оборудован']),
            ('Субподряд', ['субподряд', 'субподрядчик', 'третье лицо']),
            ('Расторжение договора', ['расторжение', 'отказ', 'прекращен']),
            ('Ответственность', ['ответственность', 'неустойка', 'штраф'])
        ]
        
        for category, keywords in categories:
            if any(keyword in header_lower for keyword in keywords):
                return category
        
        return 'Прочие риски'
    
    def extract_pattern(self, header: str) -> str:
        # паттерн риска из заголовка
        # убираем нумерацию
        pattern = re.sub(r'^\d+\.\d+\.\s+', '', header)
        return pattern
    
    def extract_recommendation(self, text: str) -> str:
        text_lower = text.lower()
        
        # прямые рекомендации из текста
        if 'рекомендуется' in text_lower or 'следует' in text_lower:
            sentences = re.split(r'[.!?]\s+', text)
            for sentence in sentences:
                if any(word in sentence.lower() for word in ['рекомендуется', 'следует', 'необходимо', 'нужно']):
                    return sentence.strip()[:100]
        
        # рекомендации на основе контекста
        if 'не согласован' in text_lower or 'отсутствует' in text_lower:
            return 'Четко согласовать условие в письменной форме'
        elif 'не указан' in text_lower or 'не определен' in text_lower:
            return 'Указать конкретные параметры и характеристики'
        elif 'может быть признан незаключенным' in text_lower:
            return 'Согласовать все существенные условия договора'
        
        return 'Провести правовой анализ условия договора'


#  для быстрого тестирования
def test_extractor():
    """Тестирует экстрактор на вашем файле"""
    print("бебра парсер...")
    
    extractor = StrictRuleBasedExtractor()
    risks = extractor.extract_risks("risks1.docx")
    
    print(f"\nРЕЗУЛЬТАТЫ: найдено {len(risks)} подрисков\n")
    
    for i, risk in enumerate(risks):
        print(f"=== РИСК {i+1} ===")
        print(f"Заголовок: {risk['header']}")
        print(f"Категория: {risk['metadata']['risk_category']}")
        print(f"Серьезность: {risk['metadata']['severity']}/10")
        print(f"Статьи: {risk['metadata']['relevant_articles'][:3]}")
        print(f"Последствия: {risk['metadata']['consequences']}")
        print(f"Описание: {risk['metadata']['description'][:100]}...")
        print()
    
    # в JSON
    with open("risks_output_strict.json", "w", encoding="utf-8") as f:
        json.dump(risks, f, ensure_ascii=False, indent=2)
    
    print(f" Результаты сохранены в risks_output_strict.json")
    
    return risks


