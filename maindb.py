# maindb_fixed.py
import json
import os
from datetime import date
from typing import List, Dict

#import
try:
    from parse_gk import parse_gk
except ImportError:
    print("parse_gk.py не найден")
    def parse_gk(filepath): return []

try:
    from risk_extractor import StrictRuleBasedExtractor
except ImportError:
    print("llm_extractor.py не найден")
    
    # заглушки
    class StrictRuleBasedExtractor:
        def extract_risks(self, filepath): 
            print("Парсер не доступен")
            return []

TODAY = str(date.today())

def main():
    print("В работе...")
    
    # ГК РФ
    print("\nПарсинг ГК...")
    try:
        norms = parse_gk("ГК_РФ_часть1111.docx")
        print(f"   Найдено {len(norms)} статей")
    except Exception as e:
        print(f"Ошибка: {e}")
        norms = []
    
    # risks
    print("\nИзвлечение рисков...")
    
    try:
        extractor = StrictRuleBasedExtractor()
        risks = extractor.extract_risks("risks1.docx")
        print(f"Извлечено {len(risks)} рисков")
        
    except Exception as e:
        print(f"Ошибка при извлечении рисков: {e}")
        risks = []
    
    # сохранение
    os.makedirs("data", exist_ok=True)
    
    knowledge_base = {
        "metadata": {
            "created": TODAY,
            "norms_count": len(norms),
            "risks_count": len(risks),
            "method": "Strict Rule-based Extractor"
        },
        "norms": norms,
        "risks": risks
    }
    
    with open("data/knowledge_base.json", "w", encoding="utf-8") as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=2)
    
    # especially for risks
    if risks:
        with open("data/risks.json", "w", encoding="utf-8") as f:
            json.dump(risks, f, ensure_ascii=False, indent=2)
    
    # Статистика
    print(f"\nСтатистика:")
    print(f"   Норм: {len(norms)}")
    print(f"   Рисков: {len(risks)}")
    
    if risks:
        print(f"\nПЕРВЫЕ 3 РИСКА:")
        for i, sample in enumerate(risks[:3]):
            print(f"\n   РИСК {i+1}:")
            print(f"     ID: {sample.get('id')}")
            print(f"     Заголовок: {sample.get('header', '')}")
            print(f"     Категория: {sample.get('metadata', {}).get('risk_category', 'N/A')}")
            print(f"     Статьи: {sample.get('metadata', {}).get('relevant_articles', [])}")
    
    print(f"\nГотово! Все в папке 'data/'")

if __name__ == "__main__":
    main()