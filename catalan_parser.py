"""
Парсер текстов на каталанском языке для задания по синтезу речи
Автоматически извлекает предложения, соответствующие критериям (7-70 слов, без цифр и спецсимволов)
"""

import re
import os
import logging
from pathlib import Path
from typing import List, Set, Generator
import hashlib
from dataclasses import dataclass

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('catalan_parser.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def count_catalan_words(sentence: str, min_word_length: int = 5) -> int:
    """
    Подсчитывает значащие слова в каталанском предложении,
    игнорируя наиболее частые служебные слова.

    Args:
        sentence: Предложение на каталанском
        min_word_length: Минимальная длина слова для учёта (по умолчанию 2)

    Returns:
        Количество значащих слов
    """
    # Список служебных слов для игнорирования (можно расширить)
    function_words = {
        # Артикли
        'el', 'la', 'els', 'les', 'un', 'una', 'uns', 'unes', 'lo', 'los', 'sa', 'ses',

        # Предлоги
        'a', 'de', 'en', 'per', 'amb', 'sense', 'sobre', 'sota', 'davant', 'darrere',
        'entre', 'fins', 'des', 'durant', 'mitjançant', 'segons', 'vers', 'cap', 'contra',

        # Союзы
        'i', 'o', 'ni', 'que', 'com', 'si', 'perquè', 'car', 'doncs', 'ja', 'tanmateix',
        'però', 'mes', 'sinó', 'malgrat', 'encara', 'fins', 'mentre', 'quan',

        # Местоимения (краткие формы)
        'em', 'et', 'es', 'ens', 'us', 'se', 'me', 'te', 'li', 'els', 'les', 'ho',
        'm\'', 't\'', 's\'', 'n\'', 'l\'',

        # Частицы
        'hi', 'ho', 'en', 'ne', 'hi', 'ha', 'és', 'son', 'era', 'eren',

        # Краткие формы глаголов
        'm\'hi', 't\'hi', 's\'hi', 'n\'hi', 'l\'hi',

        # Наиболее частые глаголы-связки (в коротких формах)
        'és', 'era', 'eren', 'som', 'sou', 'són',
    }

    # Также игнорируем слова короче min_word_length символов
    # (но только если они не являются значимыми)
    short_but_meaningful = {'si', 'no', 'va', 'vé', 'dos', 'tres', 'quatre', 'cinc'}

    # Находим все слова в предложении (с учётом каталанских символов)
    words = re.findall(r'\b[\wÀ-ÿ]+\b', sentence, re.UNICODE)

    # Фильтруем слова
    meaningful_words = []
    for word in words:
        word_lower = word.lower()

        # Пропускаем служебные слова
        if word_lower in function_words:
            continue

        # Пропускаем слова короче min_word_length символов, если они не значимые
        if len(word) < min_word_length and word_lower not in short_but_meaningful:
            continue

        meaningful_words.append(word)

    return len(meaningful_words)

@dataclass
class ParserConfig:
    """Конфигурация парсера"""
    min_words: int = 7
    max_words: int = 70
    allowed_special_chars: str = r"[\w\s,.!?;'\"àèéíïòóúüçÀÈÉÍÏÒÓÚÜÇ·¿¡]"  # Каталанские символы + пунктуация
    sentence_delimiters: str = r'[.!?;]+'  # Разделители предложений
    min_sentence_length: int = 40
    max_sentence_length: int = 400  # Максимальная длина в символах (для оптимизации)

    # Слова-маркеры начала основного текста (для удаления предисловий и т.д.)
    text_start_markers: List[str] = None

    def __post_init__(self):
        if self.text_start_markers is None:
            # Маркеры начала текста для каталанских книг
            self.text_start_markers = [
                r'CAPÍTOL\s+\d+',  # Глава
                r'CAPÍTUL\s+\d+',
                r'PRIMER\s+CAPÍTOL',
                r'INTRODUCCIÓ',
                r'PRÒLEG'
            ]

class BookParser:
    """Парсер для обработки книг на каталанском языке"""

    def __init__(self, config: ParserConfig = None):
        self.config = config or ParserConfig()
        self.processed_hashes: Set[str] = set()
        self.stats = {
            'total_sentences_found': 0,
            'valid_sentences': 0,
            'books_processed': 0,
            'sentences_by_book': {}
        }

    def normalize_text(self, text: str) -> str:
        """Нормализация текста: удаление лишних пробелов и переносов строк"""
        # Заменяем множественные переносы строк и пробелы
        text = re.sub(r'\n+', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def remove_metadata(self, text: str) -> str:
        """Удаление метаданных, сносок, примечаний"""
        # Удаляем содержимое скобок (сноски)
        text = re.sub(r'\([^)]*\)', '', text)
        text = re.sub(r'\[[^\]]*\]', '', text)

        # Удаляем цифровые сноски типа [1], [23]
        text = re.sub(r'\[\d+\]', '', text)

        # Удаляем строки, состоящие только из цифр и знаков препинания
        text = re.sub(r'^\s*[\d\s.,;:!?]*$', '', text, flags=re.MULTILINE)

        return text

    def split_into_sentences(self, text: str) -> List[str]:
        """Разбивает текст на предложения с учётом каталанской пунктуации"""
        # Заменяем сокращения с точками, чтобы они не разбивали предложения
        # abbreviations = [
        #     r'Sr\.', r'Sra\.', r'Dr\.', r'Dra\.', r'etc\.', r'p\.\s*ex\.',
        #     r'ed\.', r'vol\.', r'cap\.', r'fig\.', r'núm\.', r'pàg\.'
        # ]
        #
        # temp_text = text
        # for abbr in abbreviations:
        #     temp_text = re.sub(abbr, abbr.replace('.', '%%ABBR%%'), temp_text)

        # Разбиваем по разделителям предложений
        sentences = re.split(self.config.sentence_delimiters, text)

        # Восстанавливаем сокращения
        # restored_sentences = []
        # for sent in sentences:
        #     if sent.strip():
        #         restored = sent.replace('%%ABBR%%', '.')
        #         restored_sentences.append(restored.strip())

        # return restored_sentences
        return sentences

    def is_valid_sentence(self, sentence: str) -> bool:
        """Проверяет, соответствует ли предложение критериям"""

        if len(sentence) < self.config.min_sentence_length:
            return False

        # Проверка длины в символах (быстрая проверка)
        if len(sentence) > self.config.max_sentence_length:
            return False

        # Проверка на наличие цифр
        if re.search(r'\d', sentence):
            return False

        # Проверка на недопустимые символы
        if re.search(f'[^{self.config.allowed_special_chars}]', sentence):
            return False

        # Проверка начала предложения
        # if not sentence.lstrip()[0].isupper():
        #     return False

        # Подсчёт слов (разбиваем по пробелам и знакам препинания)
        words = count_catalan_words(sentence, min_word_length=self.config.min_words)

        if words < self.config.min_words or words > self.config.max_words:
            return False


        return True

    def clean_sentence(self, sentence: str) -> str:
        """Очистка и форматирование предложения"""

        sentence = re.sub(r'^CAP[ÍI]TOL?\s+[IVXLCDM\d]+[.:]?\s*', '', sentence, flags=re.IGNORECASE)

        patterns_to_fix = [
            (r'(\b[lLdDnNmMsS])([A-ZÀ-ÿ])', r'\1 \2'),  # lOest -> l Oest
            (r'(\b[aAeEiIoOuU])([A-ZÀ-ÿ])', r'\1 \2'),  # aOest -> a Oest
            (r'd([aeiouàèéíïòóúüAEIOUÀÈÉÍÏÒÓÚÜ])', r'd \1'),  # daquesta -> d aquesta
            (r'l([aeiouàèéíïòóúüAEIOUÀÈÉÍÏÒÓÚÜ])', r'l \1'),  # lOest -> l Oest
            (r'(\w)se(\s|$)', r'\1 se\2'),  # asense -> a sense
            (r'(\w)li(\s|$)', r'\1 li\2'),  # delli -> de lli
            (r'(\w)hi(\s|$)', r'\1 hi\2'),  # nhi -> n hi
        ]

        # 3. Удаляем изолированные запятые и точки (ошибки парсинга)
        sentence = re.sub(r'\s*,\s*se[.,]?\s*', ' ', sentence)  # ", se" или ", se."
        sentence = re.sub(r'\s*,\s*li\s*', ' ', sentence)  # ", li"
        sentence = re.sub(r'\s*,\s*nhi\s*', ' ', sentence)  # ", nhi"
        sentence = re.sub(r'\s*,\s*ad\s*', ' ', sentence)  # ", ad"

        # Удаляем лишние пробелы
        sentence = re.sub(r'\s+', ' ', sentence).strip()

        # 1. Удаляем курсив (слова между подчёркиваниями _слово_)
        # Оставляем только текст, удаляя подчёркивания
        sentence = re.sub(r'_([^_]+)_', r'\1', sentence)

        # 2. Удаляем кавычки разных типов (оставляем текст внутри)
        sentence = re.sub(r'[\"«»"“”„‟]', '', sentence)  # Удаляем только кавычки, но не апостроф

        # 3. Удаляем тире диалогов и заменяем их на запятые
        sentence = re.sub(r'\s*[-—–]\s*', ', ', sentence)

        # 4. Удаляем скобки и их содержимое (сноски, комментарии)
        sentence = re.sub(r'\([^)]*\)', '', sentence)
        sentence = re.sub(r'\[[^\]]*\]', '', sentence)

        # 5. Удаляем специальные символы, которые могут мешать TTS
        # Оставляем только буквы, цифры, пробелы и базовую пунктуацию
        sentence = re.sub(r'[*#@$%&_+=|~<>/\\©®™•·]', '', sentence)

        # 6. Удаляем многоточия и заменяем на точку
        sentence = re.sub(r'\.{2,}', '.', sentence)

        # 7. Удаляем лишние пробелы и нормализуем пробелы вокруг пунктуации
        sentence = re.sub(r'\s+', ' ', sentence).strip()

        # 8. Исправляем пробелы перед пунктуацией
        sentence = re.sub(r'\s+([,.!?;:])', r'\1', sentence)

        # 9. Добавляем пробелы после пунктуации (если нужно)
        sentence = re.sub(r'([,.!?;:])(?!\s|$)', r'\1 ', sentence)

        # 10. Проверяем наличие цифр в виде чисел (1, 2, 3...)
        # Если есть цифры, проверяем, нужно ли преобразовывать
        # Для каталанского используем num2words если нужно, но проще отбросить такие предложения
        # В функции is_valid_sentence уже есть проверка на наличие цифр

        # 11. Проверяем длину предложения (после очистки)
        words = re.findall(r'\b[\wÀ-ÿ]+\b', sentence, re.UNICODE)

        # Убеждаемся, что начинается с заглавной буквы
        if sentence and not sentence[0].isupper():
            # Ищем первую букву (пропускаем кавычки и т.д.)
            for i, char in enumerate(sentence):
                if char.isalpha():
                    sentence = sentence[i].upper() + sentence[i+1:]
                    break

        # Убеждаемся, что заканчивается точкой
        if sentence and not sentence[-1] in '.!?':
            sentence += '.'

        if len(sentence.split()) < 3:  # Минимум 3 слова после очистки
            return ""

        return sentence

    def get_sentence_hash(self, sentence: str) -> str:
        """Возвращает хеш предложения для проверки уникальности"""
        normalized = re.sub(r'\s+', ' ', sentence.lower().strip())
        return hashlib.md5(normalized.encode('utf-8')).hexdigest()

    def process_book(self, book_path: Path) -> Generator[str, None, None]:
        """Обрабатывает одну книгу и возвращает валидные предложения"""
        logger.info(f"Обработка книги: {book_path.name}")

        try:
            with open(book_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            logger.error(f"Ошибка кодировки файла {book_path}, пробуем latin-1")
            try:
                with open(book_path, 'r', encoding='latin-1') as f:
                    text = f.read()
            except Exception as e:
                logger.error(f"Не удалось прочитать файл {book_path}: {e}")
                return

        # Нормализация текста
        text = self.normalize_text(text)

        # Находим начало основного текста
        # text = self.find_text_start(text)

        # Удаляем метаданные
        text = self.remove_metadata(text)

        # Разбиваем на предложения
        raw_sentences = self.split_into_sentences(text)

        book_valid_count = 0
        for sentence in raw_sentences:
            if self.is_valid_sentence(sentence):
                cleaned = self.clean_sentence(sentence)
                sentence_hash = self.get_sentence_hash(cleaned)

                # Проверяем уникальность
                if sentence_hash not in self.processed_hashes:
                    self.processed_hashes.add(sentence_hash)
                    book_valid_count += 1
                    yield cleaned

        logger.info(f"Из книги {book_path.name} извлечено {book_valid_count} валидных предложений")
        self.stats['sentences_by_book'][book_path.name] = book_valid_count

    def process_books(self, book_paths: List[Path], output_file: Path) -> None:
        """Обрабатывает список книг и сохраняет результат в файл"""
        logger.info(f"Начало обработки {len(book_paths)} книг")

        # Инициализируем заново для перезаписи
        self.processed_hashes = set()
        self.stats = {
            'total_sentences_found': 0,
            'valid_sentences': 0,
            'books_processed': 0,
            'sentences_by_book': {}
        }

        total_valid = 0

        # Используем 'w' для перезаписи файла
        with open(output_file, 'w', encoding='utf-8') as out_f:
            for book_path in book_paths:
                if not book_path.exists():
                    logger.warning(f"Файл не найден: {book_path}")
                    continue

                self.stats['books_processed'] += 1
                book_valid = 0

                for sentence in self.process_book(book_path):
                    out_f.write(sentence + '\n')
                    book_valid += 1
                    total_valid += 1

                    # Периодически выводим прогресс
                    if total_valid % 100 == 0:
                        logger.info(f"Извлечено {total_valid} предложений...")

                logger.info(f"Книга {book_path.name}: {book_valid} предложений")

        self.stats['valid_sentences'] = total_valid
        self._save_stats()
        logger.info(f"Обработка завершена. Всего извлечено {total_valid} предложений")

    def _load_existing_hashes(self, output_file: Path) -> None:
        """Загружает хеши из существующего файла для избежания дубликатов"""
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                for line in f:
                    sentence = line.strip()
                    if sentence:
                        sentence_hash = self.get_sentence_hash(sentence)
                        self.processed_hashes.add(sentence_hash)

            existing_count = len(self.processed_hashes)
            logger.info(f"Загружено {existing_count} существующих предложений")
        except Exception as e:
            logger.error(f"Ошибка при загрузке существующих хешей: {e}")

    def _save_stats(self) -> None:
        """Сохраняет статистику работы"""
        stats_file = Path('catalan_parser_stats.txt')
        with open(stats_file, 'w', encoding='utf-8') as f:
            f.write("СТАТИСТИКА ПАРСЕРА КАТАЛАНСКИХ ТЕКСТОВ\n")
            f.write("="*50 + "\n\n")
            f.write(f"Всего обработано книг: {self.stats['books_processed']}\n")
            f.write(f"Всего извлечено предложений: {self.stats['valid_sentences']}\n")
            f.write(f"Уникальных предложений: {len(self.processed_hashes)}\n\n")

            f.write("Предложений по книгам:\n")
            for book, count in self.stats['sentences_by_book'].items():
                f.write(f"  {book}: {count}\n")

    def print_stats(self) -> None:
        """Выводит статистику в консоль"""
        print("\n" + "="*50)
        print("СТАТИСТИКА ПАРСЕРА")
        print("="*50)
        print(f"Обработано книг: {self.stats['books_processed']}")
        print(f"Извлечено предложений: {self.stats['valid_sentences']}")
        print(f"Уникальных предложений: {len(self.processed_hashes)}")

        if self.stats['sentences_by_book']:
            print("\nПо книгам:")
            for book, count in self.stats['sentences_by_book'].items():
                print(f"  {book}: {count} предложений")

def find_books_in_directory(directory: Path, extensions: List[str] = None) -> List[Path]:
    """Находит все файлы книг в указанной директории"""
    if extensions is None:
        extensions = ['.txt']

    books = []
    for ext in extensions:
        books.extend(directory.glob(f'*{ext}'))

    return sorted(books)

def main():
    """Основная функция для запуска парсера"""
    # Конфигурация
    config = ParserConfig()

    # Создаём парсер
    parser = BookParser(config)

    # Пути к книгам (укажите свои пути)
    book_directory = Path("book_catalan/processed_books")
    output_file = Path("book_catalan/parsed_sentences/catalan_sentences_all.txt")

    # Создаём выходную директорию, если её нет
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Находим все книги
    books = find_books_in_directory(book_directory)

    if not books:
        logger.error(f"В директории {book_directory} не найдено книг!")

        # Создаём пример структуры директорий
        print("\nСоздайте следующую структуру директорий:")
        print(f"{book_directory}/")
        print("  ├── llibre1.txt")
        print("  ├── llibre2.txt")
        print("  └── ...")
        return

    print(f"Найдено {len(books)} книг для обработки:")
    for book in books:
        print(f"  - {book.name}")

    # Обрабатываем книги
    parser.process_books(books, output_file)

    # Выводим статистику
    parser.print_stats()

    # Примеры извлечённых предложений
    print("\n" + "="*50)
    print("ПРИМЕРЫ ИЗВЛЕЧЁННЫХ ПРЕДЛОЖЕНИЙ:")
    print("="*50)

    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            lines = [line.strip() for line in f if line.strip()]

        if lines:
            for i in range(min(5, len(lines))):
                print(f"{i+1}. {lines[i]}")

            print(f"\nВсего предложений в файле: {len(lines)}")
            print(f"Файл сохранён: {output_file}")
    except Exception as e:
        logger.error(f"Ошибка при чтении выходного файла: {e}")

if __name__ == "__main__":
    main()