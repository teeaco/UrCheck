# main_final_fixed.py
import json
import os
import sys
import hashlib
import time
from typing import Dict, List, Any, Set, Optional
from pathlib import Path
import shutil

try:
    from tabulate import tabulate
    from vector_db import ContractRiskDB
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("\nУстановите зависимости:")
    print("pip install tabulate chromadb sentence-transformers")
    sys.exit(1)


class DataLoader:
    # ... (весь существующий код класса DataLoader без изменений)
    def __init__(self, db: ContractRiskDB):
        self.db = db
        self.data_dir = Path("./parsed_data")
    
    def wait_for_file_unlock(self, filepath: Path, max_retries: int = 5):
        for i in range(max_retries):
            try:
                with open(filepath, 'a'):
                    pass
                return True
            except (IOError, PermissionError):
                if i < max_retries - 1:
                    time.sleep(1)
                else:
                    return False
        return False
    
    def clear_database_completely(self):
        print("\nПолная очистка базы данных...")
        db_dir = Path("./chroma_db")
        if not db_dir.exists():
            print("Базы данных не существует, создаю новую")
            return
        
        try:
            if hasattr(self.db, 'client'):
                self.db.client.clear_system_cache()
        except:
            pass
        time.sleep(1)
        
        try:
            self.db.clear_database()
            print("База очищена через стандартный метод")
        except Exception as e:
            print(f"Стандартный метод не сработал: {e}")
            print("Пробую удалить файлы вручную...")
            deleted = 0
            for root, dirs, files in os.walk(db_dir):
                for file in files:
                    try:
                        filepath = Path(root) / file
                        if self.wait_for_file_unlock(filepath):
                            os.remove(filepath)
                            deleted += 1
                    except Exception as e:
                        print(f"Не удалось удалить {file}: {e}")
            print(f"Удалено файлов: {deleted}")
            if deleted == 0:
                print("Не удалось очистить базу, создаю новую...")
                self.db = ContractRiskDB(persist_directory="./chroma_db_new")
                return
    
    def fix_duplicate_ids(self, norms: List[Dict]) -> List[Dict]:
        seen_ids: Set[str] = set()
        fixed_norms = []
        duplicates_fixed = 0
        
        for norm in norms:
            norm_id = norm.get('id', '')
            if norm_id in seen_ids:
                duplicates_fixed += 1
                content = norm.get('text', '') + norm.get('header', '')
                unique_hash = hashlib.md5(content.encode()).hexdigest()[:8]
                new_id = f"{norm_id}_{unique_hash}"
                fixed_norm = norm.copy()
                fixed_norm['id'] = new_id
                fixed_norms.append(fixed_norm)
                if duplicates_fixed <= 5:
                    print(f"Исправлен дубликат: {norm_id} -> {new_id}")
            else:
                seen_ids.add(norm_id)
                fixed_norms.append(norm)
        
        if duplicates_fixed > 0:
            print(f"Всего исправлено дубликатов: {duplicates_fixed}")
        return fixed_norms
    
    def load_all_data(self) -> Dict[str, Any]:
        print("\n" + "="*60)
        print("ЗАГРУЗКА ДАННЫХ ИЗ PARSED_DATA".center(60))
        print("="*60)
        
        all_norms = []
        all_risks = []
        connections = {'risk_to_norms': {}, 'norm_to_risks': {}}
        
        norms_file = self.data_dir / "norms.json"
        if norms_file.exists():
            print(f"Загружаю нормы из {norms_file}...")
            with open(norms_file, 'r', encoding='utf-8') as f:
                norms_data = json.load(f)
            if isinstance(norms_data, list):
                print(f"Найдено норм: {len(norms_data)}")
                print("Проверяю дубликаты ID...")
                fixed_norms = self.fix_duplicate_ids(norms_data)
                all_norms.extend(fixed_norms)
                print(f"Загружено норм (после исправления дубликатов): {len(fixed_norms)}")
            else:
                print("Формат файла неверный")
        
        risks_file = self.data_dir / "risks.json"
        if risks_file.exists():
            print(f"\nЗагружаю риски из {risks_file}...")
            with open(risks_file, 'r', encoding='utf-8') as f:
                risks_data = json.load(f)
            if isinstance(risks_data, list):
                all_risks.extend(risks_data)
                print(f"Загружено рисков: {len(risks_data)}")
            else:
                print("Формат файла неверный")
        
        connections_file = self.data_dir / "connections.json"
        if connections_file.exists():
            print(f"\nЗагружаю связи из {connections_file}...")
            with open(connections_file, 'r', encoding='utf-8') as f:
                connections_data = json.load(f)
            if isinstance(connections_data, dict):
                connections.update(connections_data)
                print("Загружено связей")
        
        return {
            'norms': all_norms,
            'risks': all_risks,
            'connections': connections
        }
    
    def add_to_database(self, data: Dict[str, Any]) -> bool:
        try:
            self.clear_database_completely()
            
            if data['norms']:
                print(f"\nДобавляю {len(data['norms'])} норм в базу...")
                batch_size = 200
                for i in range(0, len(data['norms']), batch_size):
                    batch = data['norms'][i:i + batch_size]
                    norms_to_add = []
                    for norm in batch:
                        norms_to_add.append({
                            'id': norm.get('id', ''),
                            'header': norm.get('header', ''),
                            'text': norm.get('text', norm.get('body', norm.get('summary', ''))),
                            'metadata': norm.get('metadata', {})
                        })
                    try:
                        self.db.add_norms(norms_to_add)
                        print(f"Партия {i//batch_size + 1}: добавлено {len(batch)} норм")
                    except Exception as e:
                        print(f"Ошибка в партии {i//batch_size + 1}: {str(e)[:100]}...")
                print("Все нормы добавлены")
            
            if data['risks']:
                print(f"\nДобавляю {len(data['risks'])} рисков в базу...")
                risks_to_add = []
                for risk in data['risks']:
                    risks_to_add.append({
                        'id': risk.get('id', ''),
                        'header': risk.get('header', ''),
                        'text': risk.get('text', risk.get('body', risk.get('summary', ''))),
                        'metadata': risk.get('metadata', {})
                    })
                batch_size = 50
                for i in range(0, len(risks_to_add), batch_size):
                    batch = risks_to_add[i:i + batch_size]
                    self.db.add_risks(batch)
                    print(f"Партия {i//batch_size + 1}: добавлено {len(batch)} рисков")
                print("Риски добавлены")
            
            if data['connections']:
                print(f"\nДобавляю связи в базу...")
                self.db.add_connections(data['connections'])
                print("Связи добавлены")
            
            return True
        except Exception as e:
            print(f"Ошибка добавления данных: {e}")
            import traceback
            traceback.print_exc()
            return False


class SimpleRiskManager:
    def __init__(self, db: ContractRiskDB):
        self.db = db
        self.data_loaded = False
    
    def print_header(self, text: str):
        print("\n" + "="*60)
        print(f" {text.upper()} ".center(60, "="))
        print("="*60)

    # === МОДУЛЬНЫЕ МЕТОДЫ (без print/input) ===
    
    def analyze_contract_text(self, text: str) -> dict:
        """Анализирует текст договора и возвращает структурированный результат."""
        if not self.data_loaded:
            raise RuntimeError("Данные не загружены. Вызовите load_data() сначала.")
        
        text_lower = text.lower()
        doc_type = None
        if any(word in text_lower for word in ["подряд", "дноуглуб", "субподряд", "техническое задание", "генеральный подрядчик"]):
            doc_type = "contractor"
        elif any(word in text_lower for word in ["поставк", "товар", "покупатель", "поставщик"]):
            doc_type = "supplier"
        elif any(word in text_lower for word in ["услуг", "исполнитель", "заказчик"]):
            doc_type = "services_legal"
        elif any(word in text_lower for word in ["аренда", "наём", "арендодатель", "арендатор"]):
            doc_type = "lease"
        
        results = self.db.search_risks(text, n_results=20, document_type=doc_type)
        
        if not results:
            return {
                "risks": [],
                "critical": [], "high": [], "medium": [], "low": [],
                "average_severity": 0.0,
                "status": "safe",
                "message": "Риски не обнаружены",
                "total_risks": 0
            }
        
        critical = []
        high = []
        medium = []
        low = []
        for risk in results:
            severity = int(risk.get('metadata', {}).get('severity', 5))
            if severity >= 9:
                critical.append(risk)
            elif severity >= 7:
                high.append(risk)
            elif severity >= 5:
                medium.append(risk)
            else:
                low.append(risk)
        
        total_severity = sum(int(r.get('metadata', {}).get('severity', 5)) for r in results)
        avg_severity = total_severity / len(results)
        
        if avg_severity >= 8:
            status, message = "high_risk", "ВЫСОКИЙ РИСК - необходима полная переработка"
        elif avg_severity >= 6:
            status, message = "elevated_risk", "ПОВЫШЕННЫЙ РИСК - требуются существенные изменения"
        elif avg_severity >= 4:
            status, message = "moderate_risk", "УМЕРЕННЫЙ РИСК - проверьте отдельные положения"
        else:
            status, message = "low_risk", "НИЗКИЙ РИСК - договор в целом безопасен"
        
        return {
            "risks": results,
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
            "average_severity": round(avg_severity, 1),
            "status": status,
            "message": message,
            "total_risks": len(results)
        }

    def search_risks_by_query(self, query: str) -> List[Dict]:
        """Поиск рисков по запросу (без вывода)."""
        if not self.data_loaded:
            raise RuntimeError("Данные не загружены. Вызовите load_data() сначала.")
        
        query_lower = query.lower()
        doc_type = None
        if any(word in query_lower for word in ["аренда", "аренд", "наем", "наём", "арендодатель", "арендатор"]):
            doc_type = "lease"
        elif any(word in query_lower for word in ["подряд", "субподряд", "дноуглуб", "строительство", "ремонт"]):
            doc_type = "contractor"
        elif any(word in query_lower for word in ["поставк", "товар", "покупатель", "поставщик"]):
            doc_type = "supplier"
        elif any(word in query_lower for word in ["услуг", "оказание", "исполнитель", "заказчик услуг"]):
            doc_type = "services_legal"
        
        return self.db.search_risks(query, n_results=20, document_type=doc_type)

    # === МЕТОДЫ ДЛЯ КОНСОЛИ (с print/input) ===
    
    def load_data(self):
        self.print_header("ЗАГРУЗКА ДАННЫХ")
        loader = DataLoader(self.db)
        data = loader.load_all_data()
        if not data['norms'] and not data['risks']:
            print("\nНет данных для загрузки")
            return False
        
        print(f"\nОБЩАЯ СТАТИСТИКА:")
        print(f"  Норм: {len(data['norms'])}")
        print(f"  Рисков: {len(data['risks'])}")
        
        success = loader.add_to_database(data)
        if success:
            self.data_loaded = True
            print("\nДанные успешно загружены в базу!")
        return success
    
    def show_stats(self):
        self.print_header("СТАТИСТИКА СИСТЕМЫ")
        if not self.data_loaded:
            print("Данные не загружены")
            return
        try:
            stats = self.db.get_stats()
            print("\nОСНОВНЫЕ ПОКАЗАТЕЛИ:")
            print(tabulate([
                ["Всего норм ГК", stats.get('total_norms', 0)],
                ["Всего рисков", stats.get('total_risks', 0)],
                ["Всего связей", stats.get('total_connections', 0)],
                ["Уникальных статей", stats.get('unique_articles', 0)],
                ["Категорий рисков", stats.get('risk_categories', 0)]
            ], tablefmt="grid"))
        except Exception as e:
            print(f"Ошибка получения статистики: {e}")
    
    def search_risks(self):
        """Поиск рисков через консоль."""
        self.print_header("ПОИСК РИСКОВ")
        if not self.data_loaded:
            print("Данные не загружены")
            return
        query = input("\nВведите запрос для поиска рисков: ").strip()
        if not query:
            print("Запрос не может быть пустым")
            return
        try:
            results = self.search_risks_by_query(query)
            if not results:
                print("\nРиски не найдены")
                return
            print(f"\nНайдено рисков: {len(results)}")
            for i, risk in enumerate(results, 1):
                metadata = risk.get('metadata', {})
                title = metadata.get('risk_title', risk.get('header', 'Без названия'))
                category = metadata.get('risk_category', 'Не указана')
                severity = metadata.get('severity', '?')
                articles = metadata.get('relevant_articles', [])
                print(f"\n{i}. {title}")
                print(f"   Категория: {category}")
                print(f"   Серьезность: {severity}/10")
                if articles:
                    print(f"   Статьи ГК: {', '.join(articles[:3])}")
        except Exception as e:
            print(f"Ошибка поиска: {e}")
            import traceback
            traceback.print_exc()
    
    def search_norms(self):
        # ... (оставить как есть, без изменений)
        self.print_header("ПОИСК НОРМ ГК РФ")
        if not self.data_loaded:
            print("Данные не загружены")
            return
        query = input("\nВведите номер статьи или текст: ").strip()
        if not query:
            print("Запрос не может быть пустым")
            return
        try:
            if query.isdigit() or (query.lower().startswith('ст.') and query[3:].strip().isdigit()):
                article_num = query[3:].strip() if query.lower().startswith('ст.') else query
                norm = self.db.get_norm_by_article(article_num)
                if not norm:
                    norm_id = f"gk_{article_num}"
                    norm = self.db.get_norm_by_id(norm_id)
                if norm:
                    print(f"\nНАЙДЕНА: {norm.get('header', 'Без названия')}")
                    print("\nТекст статьи:")
                    print("-" * 50)
                    text = norm.get('text', '')
                    if len(text) > 500:
                        print(text[:500] + "...")
                    else:
                        print(text)
                    print("-" * 50)
                    try:
                        norm_id = norm.get('id', '')
                        related_risks = self.db.get_risks_for_norm(norm_id)
                        if related_risks:
                            print(f"\nСвязанные риски ({len(related_risks)}):")
                            for r in related_risks[:3]:
                                print(f"  • {r.get('header', 'Без названия')}")
                    except Exception as e:
                        print(f"Ошибка получения рисков: {e}")
                else:
                    print(f"\nСтатья {article_num} не найдена")
            else:
                print(f"\nИщу нормы по запросу: '{query}'")
                results = self.db.search_norms(query, n_results=5)
                if not results:
                    print("\nНормы не найдены")
                    return
                print(f"\nНайдено норм: {len(results)}")
                for i, norm in enumerate(results, 1):
                    meta = norm.get('metadata', {})
                    article_num = meta.get('article', '?')
                    print(f"\n{i}. Статья {article_num} ГК РФ")
                    print(f"   {norm.get('header', '')}")
                    text = norm.get('text', '')
                    if len(text) > 200:
                        print(f"   {text[:200]}...")
                    else:
                        print(f"   {text}")
        except Exception as e:
            print(f"Ошибка поиска: {e}")
            import traceback
            traceback.print_exc()
    
    def analyze_text(self):
        """Анализ текста через консоль."""
        self.print_header("АНАЛИЗ ТЕКСТА ДОГОВОРА")
        if not self.data_loaded:
            print("Данные не загружены")
            return
        print("\nВведите текст договора для анализа (завершите пустой строкой):")
        print("=" * 50)
        lines = []
        while True:
            try:
                line = input()
                if line == "":
                    if len(lines) >= 1:
                        break
                else:
                    lines.append(line)
            except EOFError:
                break
        text = "\n".join(lines)
        if len(text) < 30:
            print("\nТекст слишком короткий для анализа")
            return
        print(f"\nАнализирую текст ({len(text)} символов)...")
        try:
            result = self.analyze_contract_text(text)
            print(f"\nОБНАРУЖЕНО РИСКОВ: {result['total_risks']}")
            if result['critical']:
                print(f"\nКРИТИЧЕСКИЕ ({len(result['critical'])}):")
                for risk in result['critical']:
                    title = risk.get('metadata', {}).get('risk_title', risk.get('header', 'Без названия'))
                    print(f"  • {title}")
            if result['high']:
                print(f"\nВЫСОКИЕ ({len(result['high'])}):")
                for risk in result['high']:
                    title = risk.get('metadata', {}).get('risk_title', risk.get('header', 'Без названия'))
                    print(f"  • {title}")
            if result['medium']:
                print(f"\nСРЕДНИЕ ({len(result['medium'])}):")
                for risk in result['medium']:
                    title = risk.get('metadata', {}).get('risk_title', risk.get('header', 'Без названия'))
                    print(f"  • {title}")
            if result['low']:
                print(f"\nНИЗКИЕ ({len(result['low'])}):")
                for risk in result['low'][:5]:
                    title = risk.get('metadata', {}).get('risk_title', risk.get('header', 'Без названия'))
                    print(f"  • {title}")
                if len(result['low']) > 5:
                    print(f"  ... и ещё {len(result['low']) - 5} низких рисков")
            print("\n" + "="*50)
            print("ОБЩАЯ ОЦЕНКА РИСКОВ")
            print(f"Средний уровень: {result['average_severity']:.1f}/10")
            print(f"Статус: {result['message']}")
            print(f"\nРАСПРЕДЕЛЕНИЕ:")
            print(f"  Критических: {len(result['critical'])}")
            print(f"  Высоких: {len(result['high'])}")
            print(f"  Средних: {len(result['medium'])}")
            print(f"  Низких: {len(result['low'])}")
        except Exception as e:
            print(f"Ошибка анализа: {e}")
            import traceback
            traceback.print_exc()
    
    def reload_data(self):
        self.print_header("ПЕРЕЗАГРУЗКА ДАННЫХ")
        print("\nЭто удалит все текущие данные и загрузит их заново.")
        confirm = input("Продолжить? (да/нет): ").lower()
        if confirm not in ['да', 'д', 'yes', 'y']:
            print("Отменено")
            return
        self.data_loaded = False
        if self.load_data():
            print("\nПерезагрузка завершена!")
        else:
            print("\nОшибка перезагрузки")
    
    def run_menu(self):
        while True:
            print("\n" + "="*60)
            print(" СИСТЕМА АНАЛИЗА РИСКОВ ДОГОВОРОВ ".center(60, "="))
            print("="*60)
            if self.data_loaded:
                try:
                    stats = self.db.get_stats()
                    print(f"\nВ базе: {stats.get('total_risks', 0)} рисков, "
                          f"{stats.get('total_norms', 0)} норм")
                except:
                    print(f"\nДанные загружены")
            else:
                print("\nДанные не загружены")
            print("\n1. Загрузить/обновить данные")
            print("2. Показать статистику")
            print("3. Поиск рисков")
            print("4. Поиск норм ГК")
            print("5. Анализ текста договора")
            print("6. Перезагрузить данные")
            print("0. Выход")
            choice = input("\nВыберите действие: ").strip()
            if choice == "1":
                if not self.data_loaded:
                    self.load_data()
                else:
                    print("\nДанные уже загружены. Используйте 'Перезагрузить данные'")
            elif choice == "2":
                self.show_stats()
            elif choice == "3":
                self.search_risks()
            elif choice == "4":
                self.search_norms()
            elif choice == "5":
                self.analyze_text()
            elif choice == "6":
                self.reload_data()
            elif choice == "0":
                print("\nВыход...")
                break
            else:
                print("\nНеверный выбор!")
            if choice != "0":
                input("\nНажмите Enter для продолжения...")


# === ФУНКЦИИ ИНИЦИАЛИЗАЦИИ ДЛЯ МОДУЛЬНОГО ИСПОЛЬЗОВАНИЯ ===

def create_risk_manager(data_dir: str = "./parsed_data", persist_directory: str = "./chroma_db") -> SimpleRiskManager:
    """
    Создаёт и инициализирует менеджер анализа рисков.
    
    Args:
        data_dir: Папка с JSON-файлами (norms.json, risks.json, connections.json)
        persist_directory: Папка для хранения ChromaDB
    
    Returns:
        Инициализированный SimpleRiskManager
    """
    db = ContractRiskDB(persist_directory=persist_directory)
    manager = SimpleRiskManager(db)
    
    # Загрузка данных
    loader = DataLoader(db)
    loader.data_dir = Path(data_dir)
    data = loader.load_all_data()
    
    if not data['norms'] and not data['risks']:
        raise ValueError(f"Нет данных в папке {data_dir}")
    
    if not loader.add_to_database(data):
        raise RuntimeError("Ошибка загрузки данных в базу")
    
    manager.data_loaded = True
    return manager


# === ТОЧКА ВХОДА ДЛЯ КОНСОЛИ ===

def main():
    try:
        print("\n" + "="*60)
        print(" СИСТЕМА АНАЛИЗА РИСКОВ ".center(60, "="))
        print(" Работа с реальными данными ".center(60, "="))
        print("="*60)
        data_dir = Path("./parsed_data")
        if not data_dir.exists():
            print(f"\nПапка {data_dir} не найдена!")
            print("\nСоздайте папку 'parsed_data' и поместите туда:")
            print("  norms.json - нормы ГК РФ")
            print("  risks.json - риски договоров")
            print("  connections.json - связи между ними")
            return
        required_files = ['norms.json', 'risks.json', 'connections.json']
        missing_files = []
        for file in required_files:
            if not (data_dir / file).exists():
                missing_files.append(file)
        if missing_files:
            print(f"\nОтсутствуют файлы: {', '.join(missing_files)}")
            return
        print(f"\nНайдены файлы с данными: {len(required_files) - len(missing_files)} из {len(required_files)} файлов")
        db_dir = Path("./chroma_db")
        if db_dir.exists():
            print("Очищаю старую базу данных...")
            try:
                shutil.rmtree(db_dir, ignore_errors=True)
                time.sleep(1)
            except:
                db_dir = Path("./chroma_db_fresh")
        print("\nИнициализация базы данных...")
        db = ContractRiskDB(persist_directory=str(db_dir))
        manager = SimpleRiskManager(db)
        print("\n" + "="*60)
        print("АВТОМАТИЧЕСКАЯ ЗАГРУЗКА ДАННЫХ".center(60))
        print("="*60)
        if manager.load_data():
            print("\nСистема успешно загружена и готова к работе!")
            stats = manager.db.get_stats()
            print(f"   Загружено: {stats.get('total_norms', 0)} норм, "
                  f"{stats.get('total_risks', 0)} рисков")
        else:
            print("\nВозникли проблемы при загрузке данных")
            print("   Попробуйте перезагрузить данные через меню")
        manager.run_menu()
    except KeyboardInterrupt:
        print("\n\nПрограмма прервана пользователем")
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    main()