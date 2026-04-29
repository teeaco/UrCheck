# load_to_chroma.py
import json
from chroma_manager import RiskChromaManager

def main():
    print("Начинаю загрузку в ChromaDB...")
    
    # 1. Создаем менеджер
    chroma_manager = RiskChromaManager()
    
    # 2. Загружаем риски
    count = chroma_manager.add_risks_from_json("risks.json")
    
    # 3. Тестовый поиск
    print("\nТестовый поиск:")
    results = chroma_manager.search_risks("риск несогласования срока", n_results=3)
    
    for i, result in enumerate(results):
        print(f"\n{i+1}. {result['metadata']['header'][:60]}...")
        print(f"   Категория: {result['metadata']['category']}")
        print(f"   Сходство: {1 - result['score']:.2%}")
    
    # 4. Статистика
    stats = chroma_manager.get_statistics()
    print(f"\nСтатистика: {stats['total_risks']} рисков в базе")
    
    # 5. Сохраняем информацию о коллекции
    with open("data/chroma_info.json", "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)
    
    print("\nГотово. ChromaDB создана в папке 'chroma_db/'")

if __name__ == "__main__":
    main()
