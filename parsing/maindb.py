# maindb_fixed.py
import json
import os
import re
from datetime import datetime
from typing import List, Dict

try:
    from parse_gk import parse_all_gk_files, parse_gk_file
except ImportError:
    print("parse_gk.py не найден")
    def parse_all_gk_files(): return []
    def parse_gk_file(filepath): return []

try:
    from risk_extractor import StrictRuleBasedExtractor, extract_risks_from_all_files
except ImportError:
    print("risk_extractor.py не найден")
    
    # заглушки
    class StrictRuleBasedExtractor:
        def extract_risks(self, filepath, doc_type):
            print("метод extract_risks не доступен")
            return []
    
    def extract_risks_from_all_files():
        print("функция извлечения рисков не доступна")
        return []

def main():
    print("=" * 70)
    print("создание полной базы знаний")
    print("=" * 70)
    
    # 1. парсим все файлы гк рф
    print("\n1. парсинг всех файлов гк рф...")
    
    gk_files = []
    for file in os.listdir('.'):
        if (file.lower().startswith('гк') or 
            'гражданск' in file.lower() or 
            file.lower().endswith('_gk.docx')):
            if file.lower().endswith('.docx'):
                gk_files.append(file)
    
    if not gk_files:
        print("   внимание: файлы гк не найдены!")
        print("   ищу стандартные имена...")
        possible_files = [
            "гк_рф_часть1.docx",
            "гк_рф_часть2.docx",
            "гк_рф_часть3.docx",
            "гк_рф_часть4.docx"
        ]
        for file in possible_files:
            if os.path.exists(file):
                gk_files.append(file)
    
    print(f"   найдено файлов гк: {len(gk_files)}")
    for file in gk_files:
        print(f"   - {file}")
    
    # парсим 
    all_norms = []
    if gk_files:
        for gk_file in gk_files:
            print(f"\n   чтение {gk_file}...")
            try:
                norms = parse_gk_file(gk_file)
                all_norms.extend(norms)
                print(f"     найдено статей: {len(norms)}")
            except Exception as e:
                print(f"      ошибка: {e}")
    else:
        print("    нет файлов гк для парсинга!")
        all_norms = []
    
    print(f"\n    всего статей гк: {len(all_norms)}")
    
    # 2. извлекаем риски из всех 5 документов
    print("\n2. извлечение рисков из всех документов...")
    
    risk_files = [
        ("готовое решение_ риски поставщика при заключении договора по.docx", "supplier"),
        ("готовое решение_ риски покупателя при заключении договора по.docx", "customer"),
        ("готовое решение_ риски подрядчика при заключении договора по.docx", "contractor"),
        ("готовое решение_ договор возмездного оказания услуг физлицом.docx", "services_individual"),
        ("готовое решение_ договор возмездного оказания услуг между юр.docx", "services_legal")
    ]
    
    print("   проверка наличия файлов...")
    missing_files = []
    for filepath, _ in risk_files:
        if os.path.exists(filepath):
            print(f"      {os.path.basename(filepath)}")
        else:
            print(f"      {os.path.basename(filepath)} - не найден")
            missing_files.append(filepath)
    
    # извлекаем риски
    all_risks = []
    try:
        extractor = StrictRuleBasedExtractor()
        
        for filepath, doc_type in risk_files:
            if os.path.exists(filepath):
                print(f"\n   извлечение из {os.path.basename(filepath)}...")
                try:
                    risks = extractor.extract_risks(filepath, doc_type)
                    
                    for i, risk in enumerate(risks):
                        risk['id'] = f"risk_{doc_type}_{i}"
                        risk['metadata']['source_file'] = os.path.basename(filepath)
                        risk['metadata']['document_type'] = doc_type
                    
                    all_risks.extend(risks)
                    print(f"     извлечено рисков: {len(risks)}")
                except Exception as e:
                    print(f"      ошибка извлечения: {e}")
    except Exception as e:
        print(f"    ошибка при создании экстрактора: {e}")
        all_risks = []
    
    print(f"\n    всего извлечено рисков: {len(all_risks)}")
    
    # 3. создаем связи между рисками и нормами
    print("\n3. создание связей между рисками и нормами...")
    
    if all_risks and all_norms:
        connections = create_connections(all_risks, all_norms)
    else:
        connections = {
            "risk_to_norms": {},
            "norm_to_risks": {},
            "article_map": {},
            "category_map": {}
        }
    
    print(f"   создано связей: {sum(len(v) for v in connections['risk_to_norms'].values())}")
    print(f"   статей со связями: {len(connections['article_map'])}")
    
    # 4. сохраняем все данные
    print("\n4. сохранение всех данных...")
    
    os.makedirs("../data", exist_ok=True)
    
    with open("../data/norms.json", "w", encoding="utf-8") as f:
        json.dump(all_norms, f, ensure_ascii=False, indent=2)
    print("    нормы сохранены в ../data/norms.json")
    
    with open("../data/risks.json", "w", encoding="utf-8") as f:
        json.dump(all_risks, f, ensure_ascii=False, indent=2)
    print("     риски сохранены в ../data/risks.json")
    
    with open("../data/connections.json", "w", encoding="utf-8") as f:
        json.dump(connections, f, ensure_ascii=False, indent=2)
    print("    связи сохранены в ../data/connections.json")
    
    # полная база знаний
    knowledge_base = {
        "metadata": {
            "created": datetime.now().isoformat(),
            "norms_count": len(all_norms),
            "risks_count": len(all_risks),
            "connections_count": sum(len(v) for v in connections['risk_to_norms'].values()),
            "gk_files": gk_files,
            "risk_files": [f for f, _ in risk_files if os.path.exists(f)],
            "missing_files": missing_files,
            "method": "strict rule-based extractor"
        },
        "norms": all_norms,
        "risks": all_risks,
        "connections": connections
    }
    
    with open("../data/knowledge_base.json", "w", encoding="utf-8") as f:
        json.dump(knowledge_base, f, ensure_ascii=False, indent=2)
    print("    полная база знаний сохранена в ../data/knowledge_base.json")
    
    # 5. поисковый индекс
    print("\n5. создание поискового индекса...")
    search_index = create_search_index(all_risks, connections)
    with open("../data/search_index.json", "w", encoding="utf-8") as f:
        json.dump(search_index, f, ensure_ascii=False, indent=2)
    print("    поисковый индекс сохранен в ../data/search_index.json")
    
    # 6. выводим статистику
    print("\n" + "=" * 70)
    print(" статистика базы знаний")
    print("=" * 70)
    
    print(f"\n нормы гк рф:")
    print(f"   всего статей: {len(all_norms)}")
    
    if all_norms:
        article_numbers = []
        for norm in all_norms:
            article_num = norm.get('metadata', {}).get('article')
            if article_num:
                try:
                    article_numbers.append(int(article_num))
                except:
                    pass
        
        if article_numbers:
            print(f"   диапазон статей: {min(article_numbers)} - {max(article_numbers)}")
        
        keyword_stats = {}
        for norm in all_norms:
            for keyword in norm.get('metadata', {}).get('keywords', []):
                keyword_stats[keyword] = keyword_stats.get(keyword, 0) + 1
        
        if keyword_stats:
            print(f"\n   ключевые слова (топ-5):")
            for keyword, count in sorted(keyword_stats.items(), key=lambda x: x[1], reverse=True)[:5]:
                print(f"     {keyword}: {count}")
    
    print(f"\n риски:")
    print(f"   всего рисков: {len(all_risks)}")
    
    if all_risks:
        # по типам документов
        doc_types = {}
        for risk in all_risks:
            doc_type = risk.get('metadata', {}).get('document_type', 'unknown')
            doc_types[doc_type] = doc_types.get(doc_type, 0) + 1
        
        print(f"\n   по типам документов:")
        for doc_type, count in doc_types.items():
            print(f"     {doc_type}: {count}")
        
        # по категориям
        categories = {}
        for risk in all_risks:
            category = risk.get('metadata', {}).get('risk_category', 'неизвестно')
            categories[category] = categories.get(category, 0) + 1
        
        print(f"\n   по категориям (топ-10):")
        for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"     {category}: {count}")
        
        # по серьезности
        severity_counts = {1:0, 2:0, 3:0, 4:0, 5:0, 6:0, 7:0, 8:0, 9:0, 10:0}
        for risk in all_risks:
            severity = risk.get('metadata', {}).get('severity', 0)
            if 1 <= severity <= 10:
                severity_counts[severity] += 1
        
        print(f"\n   по серьезности:")
        high = sum(count for sev, count in severity_counts.items() if sev >= 8)
        medium = sum(count for sev, count in severity_counts.items() if 5 <= sev <= 7)
        low = sum(count for sev, count in severity_counts.items() if sev <= 4)
        print(f"     высокая (8-10): {high}")
        print(f"     средняя (5-7): {medium}")
        print(f"     низкая (1-4): {low}")
    
    print(f"\n связи:")
    print(f"   всего связей риск-норма: {sum(len(v) for v in connections['risk_to_norms'].values())}")
    print(f"   статей гк со связями: {len(connections['article_map'])}")
    
    if connections['article_map']:
        print(f"   статьи с наибольшим количеством связей (топ-5):")
        top_articles = sorted(connections['article_map'].items(), 
                             key=lambda x: len(x[1]), reverse=True)[:5]
        for article, risk_ids in top_articles:
            print(f"     ст. {article}: {len(risk_ids)} рисков")
    
    print(f"\n файлы:")
    print(f"   создано json файлов в папке '../data/':")
    if os.path.exists("../data"):
        data_files = [f for f in os.listdir("../data") if f.endswith(".json")]
        for file in sorted(data_files):
            size = os.path.getsize(f"../data/{file}") / 1024
            print(f"     {file}: {size:.1f} kb")
    else:
        print("     папка data не создана")
    
    # 7. примеры рисков
    print(f"\n" + "=" * 70)
    print("примеры извлеченных рисков")
    print("=" * 70)
    
    if all_risks:
        shown_docs = set()
        example_count = 0
        
        for risk in all_risks:
            doc_type = risk.get('metadata', {}).get('document_type', 'unknown')
            source_file = risk.get('metadata', {}).get('source_file', '')
            
            if doc_type not in shown_docs and example_count < 3:
                shown_docs.add(doc_type)
                example_count += 1
                
                print(f"\n пример из {source_file}:")
                print(f"   заголовок: {risk.get('header', '')[:80]}...")
                print(f"   категория: {risk.get('metadata', {}).get('risk_category', 'n/a')}")
                print(f"   серьезность: {risk.get('metadata', {}).get('severity', 0)}/10")
                
                articles = risk.get('metadata', {}).get('relevant_articles', [])
                if articles:
                    print(f"   статьи гк: {', '.join(articles[:3])}")
                
                recommendation = risk.get('metadata', {}).get('recommendation', '')
                if recommendation:
                    print(f"   рекомендация: {recommendation[:80]}...")
    else:
        print("\n риски не найдены!")
    
    print(f"\n" + "=" * 70)
    print("готово! все данные сохранены в папке '../data/'")
    print("=" * 70)

def create_connections(risks: List[Dict], norms: List[Dict]):
    """создает связи между рисками и нормами"""
    connections = {
        "risk_to_norms": {},
        "norm_to_risks": {},
        "article_map": {},
        "category_map": {}
    }
    
    # индекс норм по номерам статей
    norm_by_article = {}
    for norm in norms:
        article_num = norm.get('metadata', {}).get('article')
        if article_num:
            norm_by_article[article_num] = norm['id']
    
    for risk in risks:
        risk_id = risk['id']
        relevant_articles = risk.get('metadata', {}).get('relevant_articles', [])
        
        connections["risk_to_norms"][risk_id] = []
        
        for article_ref in relevant_articles:
            # извлекаем номер статьи из ссылки
            article_match = re.search(r'ст\.?\s*(\d+)', article_ref)
            if not article_match:
                article_match = re.search(r'стать[яи]\s*(\d+)', article_ref)
            
            if article_match:
                article_num = article_match.group(1)
                
                if article_num in norm_by_article:
                    norm_id = norm_by_article[article_num]
                    
                    connections["risk_to_norms"][risk_id].append(norm_id)
                    
                    if norm_id not in connections["norm_to_risks"]:
                        connections["norm_to_risks"][norm_id] = []
                    connections["norm_to_risks"][norm_id].append(risk_id)
                    
                    if article_num not in connections["article_map"]:
                        connections["article_map"][article_num] = []
                    connections["article_map"][article_num].append(risk_id)
        
        # map категорий
        category = risk.get('metadata', {}).get('risk_category', 'неизвестно')
        if category not in connections["category_map"]:
            connections["category_map"][category] = []
        connections["category_map"][category].append(risk_id)
    
    return connections

def create_search_index(risks: List[Dict], connections: Dict):
    """создает поисковый индекс"""
    index = {
        "by_article": {},
        "by_category": {},
        "by_severity": {"high": [], "medium": [], "low": []},
        "by_document": {},
        "by_keyword": {}
    }
    
    # индекс по статьям (из connections)
    for article_num, risk_ids in connections["article_map"].items():
        index["by_article"][article_num] = risk_ids[:10]
    
    # индекс по категориям
    for category, risk_ids in connections["category_map"].items():
        index["by_category"][category] = risk_ids[:20]
    
    # индекс по серьезности и документам
    for risk in risks:
        risk_id = risk['id']
        
        # по серьезности
        severity = risk.get('metadata', {}).get('severity', 0)
        if severity >= 8:
            index["by_severity"]["high"].append(risk_id)
        elif severity >= 5:
            index["by_severity"]["medium"].append(risk_id)
        else:
            index["by_severity"]["low"].append(risk_id)
        
        # по документам
        source_file = risk.get('metadata', {}).get('source_file', 'unknown')
        if source_file not in index["by_document"]:
            index["by_document"][source_file] = []
        index["by_document"][source_file].append(risk_id)
        
        # по ключевым словам из заголовка
        header = risk.get('header', '').lower()
        stop_words = ['риск', 'риски', 'при', 'в', 'на', 'по', 'за', 'с', 'и', 'или', 'а', 'но', 'что']
        words = re.findall(r'\b\w{4,}\b', header)
        for word in words:
            if word not in stop_words:
                if word not in index["by_keyword"]:
                    index["by_keyword"][word] = []
                if risk_id not in index["by_keyword"][word]:
                    index["by_keyword"][word].append(risk_id)
    
    return index

def quick_test():
    """быстрая проверка работы парсеров"""
    print(" быстрый тест работы")
    print("=" * 60)
    
    print("\n проверка файлов:")
    
    # файлы гк
    gk_files = [f for f in os.listdir('.') if f.lower().endswith('.docx') and ('гк' in f.lower() or 'гражданск' in f.lower())]
    print(f"   файлы гк: {len(gk_files)}")
    for file in gk_files[:3]:
        print(f"   - {file}")
    
    risk_files = [
        ("готовое решение_ риски поставщика при заключении договора по.docx", "supplier"),
        ("готовое решение_ риски покупателя при заключении договора по.docx", "customer"),
        ("готовое решение_ риски подрядчика при заключении договора по.docx", "contractor")
    ]
    
    found_risk_files = [f for f, _ in risk_files if os.path.exists(f)]
    print(f"\n   файлы рисков: {len(found_risk_files)}/{len(risk_files)}")
    for file in found_risk_files:
        print(f"     {os.path.basename(file)}")
    
    for file, _ in risk_files:
        if not os.path.exists(file):
            print(f"     {os.path.basename(file)} - отсутствует")
    
    if gk_files:
        print(f"\n тест парсинга гк ({gk_files[0]}):")
        try:
            norms = parse_gk_file(gk_files[0])
            print(f"   найдено статей: {len(norms)}")
            if norms:
                print(f"   первая статья: {norms[0].get('header', '')[:60]}...")
        except Exception as e:
            print(f"   ошибка: {e}")
    
    if found_risk_files:
        print(f"\n тест извлечения рисков ({os.path.basename(found_risk_files[0])}):")
        try:
            extractor = StrictRuleBasedExtractor()
            risks = extractor.extract_risks(found_risk_files[0], "test")
            print(f"   найдено рисков: {len(risks)}")
            if risks:
                print(f"   первый риск: {risks[0].get('header', '')[:60]}...")
        except Exception as e:
            print(f"   ошибка: {e}")
    
    print("\n" + "=" * 60)
    print("для создания полной базы знаний запустите main()")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        quick_test()
    else:
        main()