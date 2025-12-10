# main_final_fixed.py
import json
import os
import sys
import hashlib
import time
from typing import Dict, List, Any, Set
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
    def __init__(self, db: ContractRiskDB):
        self.db = db
        self.data_dir = Path("./parsed_data")
    
    def wait_for_file_unlock(self, filepath: Path, max_retries: int = 5):
        """Ждет, пока файл разблокируется"""
        for i in range(max_retries):
            try:
                # Пробуем открыть файл на запись
                with open(filepath, 'a'):
                    pass
                return True
            except (IOError, PermissionError):
                if i < max_retries - 1:
                    print(f"  Файл заблокирован, жду 1 секунду... (попытка {i+1}/{max_retries})")
                    time.sleep(1)
                else:
                    return False
        return False
    
    def clear_database_completely(self):
        """Полностью очищает базу данных"""
        print("\n🧹 Полная очистка базы данных...")
        
        db_dir = Path("./chroma_db")
        
        if not db_dir.exists():
            print("✓ Базы данных не существует, создаю новую")
            return
        
        # Закрываем соединение с базой
        try:
            if hasattr(self.db, 'client'):
                self.db.client.clear_system_cache()
        except:
            pass
        
        # Ждем немного
        time.sleep(1)
        
        # Пробуем удалить файлы
        try:
            # Пробуем стандартный метод очистки
            self.db.clear_database()
            print("✓ База очищена через стандартный метод")
        except Exception as e:
            print(f"  Стандартный метод не сработал: {e}")
            
            # Пробуем удалить файлы вручную
            print("  Пробую удалить файлы вручную...")
            deleted = 0
            for root, dirs, files in os.walk(db_dir):
                for file in files:
                    try:
                        filepath = Path(root) / file
                        if self.wait_for_file_unlock(filepath):
                            os.remove(filepath)
                            deleted += 1
                    except Exception as e:
                        print(f"    Не удалось удалить {file}: {e}")
            
            print(f"  Удалено файлов: {deleted}")
            
            if deleted == 0:
                print("  ❗ Не удалось очистить базу, создаю новую...")
                # Создаем новую базу в другой директории
                self.db = ContractRiskDB(persist_directory="./chroma_db_new")
                return
    
    def fix_duplicate_ids(self, norms: List[Dict]) -> List[Dict]:
        """Исправляет дублирующиеся ID в нормах"""
        seen_ids: Set[str] = set()
        fixed_norms = []
        duplicates_fixed = 0
        
        for norm in norms:
            norm_id = norm.get('id', '')
            
            # Если ID уже встречался, создаем уникальный
            if norm_id in seen_ids:
                duplicates_fixed += 1
                # Создаем уникальный ID на основе содержимого
                content = norm.get('text', '') + norm.get('header', '')
                unique_hash = hashlib.md5(content.encode()).hexdigest()[:8]
                new_id = f"{norm_id}_{unique_hash}"
                
                # Создаем копию нормы с новым ID
                fixed_norm = norm.copy()
                fixed_norm['id'] = new_id
                fixed_norms.append(fixed_norm)
                
                if duplicates_fixed <= 5:  # Показываем только первые 5
                    print(f"  Исправлен дубликат: {norm_id} -> {new_id}")
            else:
                seen_ids.add(norm_id)
                fixed_norms.append(norm)
        
        if duplicates_fixed > 0:
            print(f"\n  Всего исправлено дубликатов: {duplicates_fixed}")
        
        return fixed_norms
    
    def load_all_data(self) -> Dict[str, Any]:
        """Загружает все данные из parsed_data"""
        print("\n" + "="*60)
        print("ЗАГРУЗКА ДАННЫХ ИЗ PARSED_DATA".center(60))
        print("="*60)
        
        all_norms = []
        all_risks = []
        connections = {'risk_to_norms': {}, 'norm_to_risks': {}}
        
        # Загружаем нормы
        norms_file = self.data_dir / "norms.json"
        if norms_file.exists():
            print(f"📄 Загружаю нормы из {norms_file}...")
            with open(norms_file, 'r', encoding='utf-8') as f:
                norms_data = json.load(f)
            
            if isinstance(norms_data, list):
                print(f"  Найдено норм: {len(norms_data)}")
                
                # Исправляем дубликаты
                print("  🔍 Проверяю дубликаты ID...")
                fixed_norms = self.fix_duplicate_ids(norms_data)
                
                all_norms.extend(fixed_norms)
                print(f"  ✅ Загружено норм (после исправления дубликатов): {len(fixed_norms)}")
            else:
                print(f"  ❗ Формат файла неверный")
        
        # Загружаем риски
        risks_file = self.data_dir / "risks.json"
        if risks_file.exists():
            print(f"\n📄 Загружаю риски из {risks_file}...")
            with open(risks_file, 'r', encoding='utf-8') as f:
                risks_data = json.load(f)
            
            if isinstance(risks_data, list):
                all_risks.extend(risks_data)
                print(f"  ✅ Загружено рисков: {len(risks_data)}")
            else:
                print(f"  ❗ Формат файла неверный")
        
        # Загружаем связи
        connections_file = self.data_dir / "connections.json"
        if connections_file.exists():
            print(f"\n📄 Загружаю связи из {connections_file}...")
            with open(connections_file, 'r', encoding='utf-8') as f:
                connections_data = json.load(f)
            
            if isinstance(connections_data, dict):
                connections.update(connections_data)
                print(f"  ✅ Загружено связей")
        
        return {
            'norms': all_norms,
            'risks': all_risks,
            'connections': connections
        }
    
    def add_to_database(self, data: Dict[str, Any]) -> bool:
        """Добавляет данные в базу"""
        try:
            # Очищаем базу полностью
            self.clear_database_completely()
            
            # Добавляем нормы партиями
            if data['norms']:
                print(f"\n📤 Добавляю {len(data['norms'])} норм в базу...")
                
                # Разбиваем на партии
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
                        print(f"  📦 Партия {i//batch_size + 1}: добавлено {len(batch)} норм")
                    except Exception as e:
                        print(f"  ❗ Ошибка в партии {i//batch_size + 1}: {str(e)[:100]}...")
                
                print(f"  ✅ Все нормы добавлены")
            
            # Добавляем риски
            if data['risks']:
                print(f"\n📤 Добавляю {len(data['risks'])} рисков в базу...")
                risks_to_add = []
                for risk in data['risks']:
                    risks_to_add.append({
                        'id': risk.get('id', ''),
                        'header': risk.get('header', ''),
                        'text': risk.get('text', risk.get('body', risk.get('summary', ''))),
                        'metadata': risk.get('metadata', {})
                    })
                
                # Добавляем партиями
                batch_size = 50
                for i in range(0, len(risks_to_add), batch_size):
                    batch = risks_to_add[i:i + batch_size]
                    self.db.add_risks(batch)
                    print(f"  📦 Партия {i//batch_size + 1}: добавлено {len(batch)} рисков")
                
                print(f"  ✅ Риски добавлены")
            
            # Добавляем связи
            if data['connections']:
                print(f"\n🔗 Добавляю связи в базу...")
                self.db.add_connections(data['connections'])
                print(f"  ✅ Связи добавлены")
            
            return True
            
        except Exception as e:
            print(f"❗ Ошибка добавления данных: {e}")
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
    
    def load_data(self):
        """Загружает данные при запуске"""
        self.print_header("ЗАГРУЗКА ДАННЫХ")
        
        loader = DataLoader(self.db)
        data = loader.load_all_data()
        
        if not data['norms'] and not data['risks']:
            print("\n❗ Нет данных для загрузки")
            return False
        
        print(f"\n📊 ОБЩАЯ СТАТИСТИКА:")
        print(f"  📄 Норм: {len(data['norms'])}")
        print(f"  ⚠️  Рисков: {len(data['risks'])}")
        
        success = loader.add_to_database(data)
        if success:
            self.data_loaded = True
            print("\n✅ Данные успешно загружены в базу!")
        
        return success
    
    def show_stats(self):
        """Показывает статистику системы"""
        self.print_header("СТАТИСТИКА СИСТЕМЫ")
        
        if not self.data_loaded:
            print("❗ Данные не загружены")
            return
        
        try:
            stats = self.db.get_stats()
            
            print("\n📊 ОСНОВНЫЕ ПОКАЗАТЕЛИ:")
            print(tabulate([
                ["Всего норм ГК", stats.get('total_norms', 0)],
                ["Всего рисков", stats.get('total_risks', 0)],
                ["Всего связей", stats.get('total_connections', 0)],
                ["Уникальных статей", stats.get('unique_articles', 0)],
                ["Категорий рисков", stats.get('risk_categories', 0)]
            ], tablefmt="grid"))
            
        except Exception as e:
            print(f"❗ Ошибка получения статистики: {e}")
    
    def search_risks(self):
        """Поиск рисков"""
        self.print_header("ПОИСК РИСКОВ")
        
        if not self.data_loaded:
            print("❗ Данные не загружены")
            return
        
        query = input("\n🔍 Введите запрос для поиска рисков: ").strip()
        if not query:
            print("❗ Запрос не может быть пустым")
            return
        
        try:
            results = self.db.search_risks(query, n_results=10)
            
            if not results:
                print("\n❌ Риски не найдены")
                return
            
            print(f"\n✅ Найдено рисков: {len(results)}")
            
            for i, risk in enumerate(results, 1):
                metadata = risk.get('metadata', {})
                
                print(f"\n{i}. {metadata.get('risk_title', risk.get('header', 'Без названия'))}")
                print(f"   📁 Категория: {metadata.get('risk_category', 'Не указана')}")
                print(f"   ⚠️  Серьезность: {metadata.get('severity', '?')}/10")
                
                articles = metadata.get('relevant_articles', [])
                if articles:
                    print(f"   📚 Статьи ГК: {', '.join(articles[:3])}")
                
                if i >= 5:  # Показываем только первые 5
                    print(f"\n   ... и еще {len(results) - 5} результатов")
                    break
        
        except Exception as e:
            print(f"❗ Ошибка поиска: {e}")
    
    def search_norms(self):
        """Поиск норм"""
        self.print_header("ПОИСК НОРМ ГК РФ")
        
        if not self.data_loaded:
            print("❗ Данные не загружены")
            return
        
        query = input("\n🔍 Введите номер статьи или текст: ").strip()
        if not query:
            print("❗ Запрос не может быть пустым")
            return
        
        try:
            # Поиск по номеру статьи
            if query.isdigit() or (query.lower().startswith('ст.') and query[3:].strip().isdigit()):
                article_num = query[3:].strip() if query.lower().startswith('ст.') else query
                
                # Пробуем найти норму
                try:
                    norm = self.db.get_norm_by_article(article_num)
                except:
                    # Ищем по ID
                    norm_id = f"gk_{article_num}"
                    try:
                        norm = self.db.get_norm_by_id(norm_id)
                    except:
                        norm = None
                
                if norm:
                    print(f"\n✅ НАЙДЕНА: {norm.get('header', 'Без названия')}")
                    print("\n📄 Текст статьи:")
                    print("-" * 50)
                    text = norm.get('text', '')
                    if len(text) > 500:
                        print(text[:500] + "...")
                    else:
                        print(text)
                    print("-" * 50)
                    
                    # Показываем связанные риски
                    try:
                        norm_id = norm.get('id', '')
                        related_risks = self.db.get_risks_for_norm(norm_id)
                        if related_risks:
                            print(f"\n🔗 Связанные риски ({len(related_risks)}):")
                            for risk in related_risks[:3]:
                                meta = risk.get('metadata', {})
                                print(f"  • {meta.get('risk_title', 'Без названия')}")
                    except:
                        pass
                else:
                    print(f"\n❌ Статья {article_num} не найдена")
            
            # Поиск по тексту
            else:
                print(f"\n🔍 Ищу нормы по запросу: '{query}'")
                results = self.db.search_norms(query, n_results=5)
                
                if not results:
                    print("\n❌ Нормы не найдены")
                    return
                
                print(f"\n✅ Найдено норм: {len(results)}")
                
                for i, norm in enumerate(results, 1):
                    metadata = norm.get('metadata', {})
                    article_num = metadata.get('article', '?')
                    
                    print(f"\n{i}. Статья {article_num} ГК РФ")
                    print(f"   {norm.get('header', '')}")
                    
                    text = norm.get('text', '')
                    if len(text) > 200:
                        print(f"   {text[:200]}...")
                    else:
                        print(f"   {text}")
        
        except Exception as e:
            print(f"❗ Ошибка поиска: {e}")
    
    def analyze_text(self):
        """Анализ текста договора"""
        self.print_header("АНАЛИЗ ТЕКСТА ДОГОВОРА")
        
        if not self.data_loaded:
            print("❗ Данные не загружены")
            return
        
        print("\n📝 Введите текст договора для анализа (завершите пустой строкой):")
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
            print("\n❗ Текст слишком короткий для анализа")
            return
        
        print(f"\n🔍 Анализирую текст ({len(text)} символов)...")
        
        try:
            results = self.db.search_risks(text, n_results=15)
            
            if not results:
                print("\n✅ Риски не обнаружены - договор безопасен!")
                return
            
            # Группируем по серьезности
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
            
            print(f"\n⚠️  ОБНАРУЖЕНО РИСКОВ: {len(results)}")
            
            if critical:
                print(f"\n🔴 КРИТИЧЕСКИЕ ({len(critical)}):")
                for risk in critical[:3]:
                    title = risk.get('metadata', {}).get('risk_title', 'Без названия')
                    print(f"  • {title}")
            
            if high:
                print(f"\n🟠 ВЫСОКИЕ ({len(high)}):")
                for risk in high[:3]:
                    title = risk.get('metadata', {}).get('risk_title', 'Без названия')
                    print(f"  • {title}")
            
            if medium:
                print(f"\n🟡 СРЕДНИЕ ({len(medium)}):")
                for risk in medium[:2]:
                    title = risk.get('metadata', {}).get('risk_title', 'Без названия')
                    print(f"  • {title}")
            
            # Общая оценка
            total_severity = sum(int(r.get('metadata', {}).get('severity', 5)) for r in results)
            avg_severity = total_severity / len(results) if results else 0
            
            print("\n" + "="*50)
            print("📊 ОБЩАЯ ОЦЕНКА РИСКОВ")
            print(f"Средний уровень: {avg_severity:.1f}/10")
            
            if avg_severity >= 8:
                print("Статус: 🔴 ВЫСОКИЙ РИСК - необходима полная переработка")
            elif avg_severity >= 6:
                print("Статус: 🟠 ПОВЫШЕННЫЙ РИСК - требуются существенные изменения")
            elif avg_severity >= 4:
                print("Статус: 🟡 УМЕРЕННЫЙ РИСК - проверьте отдельные положения")
            else:
                print("Статус: 🟢 НИЗКИЙ РИСК - договор в целом безопасен")
            
            print(f"\n📈 Распределение:")
            print(f"  🔴 Критических: {len(critical)}")
            print(f"  🟠 Высоких: {len(high)}")
            print(f"  🟡 Средних: {len(medium)}")
            print(f"  🟢 Низких: {len(low)}")
            
        except Exception as e:
            print(f"❗ Ошибка анализа: {e}")
    
    def reload_data(self):
        """Перезагружает данные"""
        self.print_header("ПЕРЕЗАГРУЗКА ДАННЫХ")
        
        print("\n⚠️  Это удалит все текущие данные и загрузит их заново.")
        confirm = input("Продолжить? (да/нет): ").lower()
        
        if confirm not in ['да', 'д', 'yes', 'y']:
            print("Отменено")
            return
        
        self.data_loaded = False
        if self.load_data():
            print("\n✅ Перезагрузка завершена!")
        else:
            print("\n❌ Ошибка перезагрузки")
    
    def run_menu(self):
        """Основное меню"""
        while True:
            print("\n" + "="*60)
            print(" СИСТЕМА АНАЛИЗА РИСКОВ ДОГОВОРОВ ".center(60, "="))
            print("="*60)
            
            if self.data_loaded:
                try:
                    stats = self.db.get_stats()
                    print(f"\n📊 В базе: {stats.get('total_risks', 0)} рисков, "
                          f"{stats.get('total_norms', 0)} норм")
                except:
                    print(f"\n📊 Данные загружены")
            else:
                print("\n⚠️  Данные не загружены")
            
            print("\n1. 📂 Загрузить/обновить данные")
            print("2. 📊 Показать статистику")
            print("3. 🔍 Поиск рисков")
            print("4. 📚 Поиск норм ГК")
            print("5. 📝 Анализ текста договора")
            print("6. 🔄 Перезагрузить данные")
            print("0. 🚪 Выход")
            
            choice = input("\n🎯 Выберите действие: ").strip()
            
            if choice == "1":
                if not self.data_loaded:
                    self.load_data()
                else:
                    print("\nℹ️  Данные уже загружены. Используйте 'Перезагрузить данные'")
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
                print("\n👋 Выход...")
                break
            else:
                print("\n❌ Неверный выбор!")
            
            if choice != "0":
                input("\n⏎ Нажмите Enter для продолжения...")

def main():
    try:
        print("\n" + "="*60)
        print(" СИСТЕМА АНАЛИЗА РИСКОВ ".center(60, "="))
        print(" Работа с реальными данными ".center(60, "="))
        print("="*60)
        
        # Проверяем наличие папки с данными
        data_dir = Path("./parsed_data")
        if not data_dir.exists():
            print(f"\n❌ Папка {data_dir} не найдена!")
            print("\nСоздайте папку 'parsed_data' и поместите туда:")
            print("  📄 norms.json - нормы ГК РФ")
            print("  ⚠️  risks.json - риски договоров")
            print("  🔗 connections.json - связи между ними")
            return
        
        # Проверяем наличие файлов
        required_files = ['norms.json', 'risks.json', 'connections.json']
        missing_files = []
        for file in required_files:
            if not (data_dir / file).exists():
                missing_files.append(file)
        
        if missing_files:
            print(f"\n❌ Отсутствуют файлы: {', '.join(missing_files)}")
            return
        
        print("\n📂 Найдены файлы с данными:")
        print(f"  ✅ {len(required_files) - len(missing_files)} из {len(required_files)} файлов")

        
        # Удаляем старую базу, если она есть и заблокирована
        db_dir = Path("./chroma_db")
        if db_dir.exists():
            print("🧹 Очищаю старую базу данных...")
            try:
                shutil.rmtree(db_dir, ignore_errors=True)
                time.sleep(1)
            except:
                print("  ⚠️  Не удалось полностью очистить, создаю новую базу...")
                # Используем другую директорию
                db_dir = Path("./chroma_db_fresh")
        
        # Инициализируем базу
        print("\n🔧 Инициализация базы данных...")
        db = ContractRiskDB(persist_directory=str(db_dir))
        manager = SimpleRiskManager(db)
        
        # Автозагрузка данных при старте
        print("\n" + "="*60)
        print("АВТОМАТИЧЕСКАЯ ЗАГРУЗКА ДАННЫХ".center(60))
        print("="*60)
        
        if manager.load_data():
            print("\n✅ Система успешно загружена и готова к работе!")
            print(f"   📊 Загружено: {manager.db.get_stats().get('total_norms', 0)} норм, "
                  f"{manager.db.get_stats().get('total_risks', 0)} рисков")
        else:
            print("\n⚠️  Возникли проблемы при загрузке данных")
            print("   Попробуйте перезагрузить данные через меню")
        
        # Запускаем интерактивное меню
        manager.run_menu()
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Программа прервана пользователем")
    except Exception as e:
        print(f"\n💥 Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        input("\n⏎ Нажмите Enter для выхода...")

if __name__ == "__main__":
    main()