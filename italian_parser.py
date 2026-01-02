"""
Парсер текстов на итальянском языке для задания по синтезу речи
Основан на опыте парсинга каталанского, адаптирован для итальянского
"""

import re
import os
import logging
from pathlib import Path
from typing import List, Set, Generator, Dict, Tuple
import hashlib
from langdetect import detect, LangDetectException

# ============================================================================
# КОНФИГУРАЦИЯ (все настройки здесь)
# ============================================================================

# Пути к файлам и папкам
BOOKS_DIR = Path("book_italian/parsed_books")  # Папка с исходными книгами
OUTPUT_DIR = Path("book_italian/parsed_sentences")  # Папка для результатов
OUTPUT_FILE = OUTPUT_DIR / "italian_sentences_all.txt"  # Основной файл с предложениями
FILTERED_FILE = OUTPUT_DIR / "italian_filtered.txt"  # Файл после фильтрации языка
CLEANED_FILE = OUTPUT_DIR / "italian_cleaned.txt"  # Окончательный файл
LOG_DIR = Path("logs")  # Папка для логов

# Файлы для логов и статистики
LANGUAGE_LOG = LOG_DIR / "language_check.log"  # Лог проверки языка
CLEANING_LOG = LOG_DIR / "cleaning_log.txt"  # Лог очистки
STATS_FILE = LOG_DIR / "parser_stats.txt"  # Общая статистика

# Критерии предложений
MIN_WORDS = 7
MAX_WORDS = 70
MIN_CHARS = 40  # Минимальная длина в символах
MAX_CHARS = 500  # Максимальная длина в символах

# Настройки для проверки языка (если включена)
ENABLE_LANGUAGE_CHECK = True  # Включить проверку языка
LANGUAGE_CHECK_SAMPLE_SIZE = 50000  # Проверять только первые N предложений

# Разделители предложений для итальянского
SENTENCE_DELIMITERS = r'[.!?;…]+'
ALLOWED_SPECIAL_CHARS = r"[\w\s,.!?;:'\"àèéìíîòóùúÀÈÉÌÍÎÒÓÙÚ\-]"  # Итальянские символы + пунктуация

# Служебные слова для итальянского (для улучшенного подсчёта слов)
ITALIAN_FUNCTION_WORDS = {
    # Артикли
    'il', 'lo', 'la', 'i', 'gli', 'le', 'un', 'uno', 'una', 'un\'',

    # Предлоги
    'di', 'a', 'da', 'in', 'con', 'su', 'per', 'tra', 'fra',

    # Союзы
    'e', 'o', 'ma', 'se', 'perché', 'che', 'come', 'quando', 'dove',

    # Местоимения (краткие формы)
    'mi', 'ti', 'ci', 'vi', 'lo', 'la', 'li', 'le', 'gli', 'ne',
    'm\'', 't\'', 'c\'', 'v\'', 'l\'',

    # Частицы и вспомогательные глаголы
    'è', 'sono', 'era', 'erano', 'ha', 'hanno', 'aveva',
}

# Маркеры начала основного текста
TEXT_START_MARKERS = [
    r'CAPITOLO\s+\d+',
    r'Capitolo\s+\d+',
    r'INTRODUZIONE',
    r'PROLOGO',
    r'PREFACE',
    r'INDICE',
]

# Настройка логирования
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - %(levelname)s - %(message)s',
#     handlers=[
#         logging.FileHandler(LOG_DIR / 'italian_parser.log', encoding='utf-8'),
#         logging.StreamHandler()
#     ]
# )
# logger = logging.getLogger(__name__)


# ============================================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================================

def count_italian_words(sentence: str, min_word_length: int = 5) -> int:
    """
    Подсчитывает значащие слова в итальянском предложении,
    игнорируя служебные слова.
    """
    short_but_meaningful = {'sì', 'no', 'va', 'và', 'tre', 'due', 'qui', 'lì'}

    words = re.findall(r'\b[\wÀ-ÿ]+\b', sentence, re.UNICODE)

    meaningful_words = []
    for word in words:
        word_lower = word.lower()

        if word_lower in ITALIAN_FUNCTION_WORDS:
            continue

        if len(word) < min_word_length and word_lower not in short_but_meaningful:
            continue

        meaningful_words.append(word)

    return len(meaningful_words)


def get_sentence_hash(sentence: str) -> str:
    """Возвращает хеш предложения для проверки уникальности"""
    normalized = re.sub(r'\s+', ' ', sentence.lower().strip())
    return hashlib.md5(normalized.encode('utf-8')).hexdigest()


def normalize_text(text: str) -> str:
    """Нормализация текста: удаление лишних пробелов и переносов"""
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def remove_metadata(text: str) -> str:
    """Удаление метаданных, сносок, примечаний"""
    text = re.sub(r'\([^)]*\)', '', text)
    text = re.sub(r'\[[^\]]*\]', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    text = re.sub(r'^\s*[\d\s.,;:!?]*$', '', text, flags=re.MULTILINE)
    return text


def split_into_sentences(text: str) -> List[str]:
    """Разбивает текст на предложения с учётом итальянской пунктуации"""
    sentences = re.split(SENTENCE_DELIMITERS, text)
    return [s.strip() for s in sentences if s.strip()]


# ============================================================================
# ОСНОВНОЙ КЛАСС ПАРСЕРА
# ============================================================================

class ItalianBookParser:
    """Парсер для обработки книг на итальянском языке"""

    def __init__(self):
        self.processed_hashes: Set[str] = set()
        self.stats = {
            'total_books': 0,
            'total_sentences': 0,
            'valid_sentences': 0,
            'sentences_by_book': {},
            'rejected': {
                'too_short': 0,
                'too_long': 0,
                'has_digits': 0,
                'bad_chars': 0,
                'not_upper': 0,
                'word_count': 0,
                'duplicate': 0,
            }
        }

    def is_valid_sentence(self, sentence: str) -> Tuple[bool, str]:
        """Проверяет, соответствует ли предложение критериям"""

        if len(sentence) < MIN_CHARS:
            return False, "too_short"

        if len(sentence) > MAX_CHARS:
            return False, "too_long"

        if re.search(r'\d', sentence):
            return False, "has_digits"

        if re.search(f'[^{ALLOWED_SPECIAL_CHARS}]', sentence):
            return False, "bad_chars"

        words = count_italian_words(sentence)
        if words < MIN_WORDS or words > MAX_WORDS:
            return False, "word_count"

        sentence_hash = get_sentence_hash(sentence)
        if sentence_hash in self.processed_hashes:
            return False, "duplicate"

        return True, ""

    def clean_sentence(self, sentence: str) -> str:
        """Очистка и форматирование предложения"""

        # Удаляем маркеры глав
        for marker in TEXT_START_MARKERS:
            sentence = re.sub(marker, '', sentence, flags=re.IGNORECASE)

        # Исправляем слипшиеся слова с апострофами (сохраняем апострофы!)
        patterns_to_fix = [
            (r'(\b[lLdDnNmMsS])([A-ZÀ-ÿ])', r'\1 \2'),  # l'Ovest -> l' Ovest
            (r'(\b[aAeEiIoOuU])([A-ZÀ-ÿ])', r'\1 \2'),  # aOvest -> a Ovest
        ]

        for pattern, replacement in patterns_to_fix:
            sentence = re.sub(pattern, replacement, sentence)

        # Удаляем курсив (но сохраняем текст)
        sentence = re.sub(r'_([^_]+)_', r'\1', sentence)

        # Удаляем кавычки разных типов (но сохраняем апострофы)
        sentence = re.sub(r'[\"«»"“”„‟]', '', sentence)

        # Удаляем тире диалогов, заменяем на запятые
        sentence = re.sub(r'\s*[-—–]\s*', ', ', sentence)

        # Удаляем скобки и их содержимое
        sentence = re.sub(r'\([^)]*\)', '', sentence)
        sentence = re.sub(r'\[[^\]]*\]', '', sentence)

        # Удаляем специальные символы, которые могут мешать TTS
        sentence = re.sub(r'[*#@$%&_+=|~<>/\\©®™•·]', '', sentence)

        # Заменяем многоточия на точку
        sentence = re.sub(r'\.{2,}', '.', sentence)

        # Нормализуем пробелы
        sentence = re.sub(r'\s+', ' ', sentence).strip()

        # Исправляем пробелы перед пунктуацией
        sentence = re.sub(r'\s+([,.!?;:])', r'\1', sentence)

        # Добавляем пробелы после пунктуации
        sentence = re.sub(r'([,.!?;:])(?!\s|$)', r'\1 ', sentence)

        # Убеждаемся, что начинается с заглавной буквы
        if sentence and not sentence[0].isupper():
            for i, char in enumerate(sentence):
                if char.isalpha():
                    sentence = sentence[i].upper() + sentence[i + 1:]
                    break

        # Убеждаемся, что заканчивается точкой
        if sentence and not sentence[-1] in '.!?':
            sentence += '.'

        return sentence

    def process_book(self, book_path: Path) -> Generator[str, None, None]:
        """Обрабатывает одну книгу и возвращает валидные предложения"""
        print(f"Обработка книги: {book_path.name}")

        try:
            with open(book_path, 'r', encoding='utf-8') as f:
                text = f.read()
        except Exception as e:
            print(f"Не удалось прочитать файл {book_path}: {e}")
            return

        text = normalize_text(text)
        text = remove_metadata(text)
        sentences = split_into_sentences(text)

        book_valid_count = 0
        for sentence in sentences:
            is_valid, reason = self.is_valid_sentence(sentence)

            if is_valid:
                cleaned = self.clean_sentence(sentence)
                sentence_hash = get_sentence_hash(cleaned)

                if sentence_hash not in self.processed_hashes:
                    self.processed_hashes.add(sentence_hash)
                    book_valid_count += 1
                    self.stats['valid_sentences'] += 1
                    yield cleaned
            else:
                self.stats['rejected'][reason] += 1

        self.stats['sentences_by_book'][book_path.name] = book_valid_count
        print(f"Из книги {book_path.name} извлечено {book_valid_count} валидных предложений")

    def process_all_books(self, book_paths: List[Path]) -> None:
        """Обрабатывает все книги и сохраняет результат"""
        print(f"Начало обработки {len(book_paths)} книг")

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        LOG_DIR.mkdir(parents=True, exist_ok=True)

        self.processed_hashes = set()
        self.stats = {
            'total_books': len(book_paths),
            'total_sentences': 0,
            'valid_sentences': 0,
            'sentences_by_book': {},
            'rejected': {
                'too_short': 0,
                'too_long': 0,
                'has_digits': 0,
                'bad_chars': 0,
                'not_upper': 0,
                'word_count': 0,
                'duplicate': 0,
            }
        }

        with open(OUTPUT_FILE, 'w', encoding='utf-8') as out_f:
            for book_path in book_paths:
                if not book_path.exists():
                    print(f"Файл не найден: {book_path}")
                    continue

                book_valid = 0
                for sentence in self.process_book(book_path):
                    out_f.write(sentence + '\n')
                    book_valid += 1

                    if self.stats['valid_sentences'] % 1000 == 0:
                        print(f"Извлечено {self.stats['valid_sentences']} предложений...")

        self._save_stats()
        print(f"Обработка завершена. Всего извлечено {self.stats['valid_sentences']} предложений")

    def _save_stats(self) -> None:
        """Сохраняет статистику работы"""
        with open(STATS_FILE, 'w', encoding='utf-8') as f:
            f.write("СТАТИСТИКА ПАРСЕРА ИТАЛЬЯНСКИХ ТЕКСТОВ\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Обработано книг: {self.stats['total_books']}\n")
            f.write(f"Валидных предложений: {self.stats['valid_sentences']}\n")
            f.write(f"Уникальных предложений: {len(self.processed_hashes)}\n\n")

            f.write("Отклонённые предложения:\n")
            for reason, count in self.stats['rejected'].items():
                f.write(f"  {reason}: {count}\n")

            f.write("\nПредложений по книгам:\n")
            for book, count in self.stats['sentences_by_book'].items():
                f.write(f"  {book}: {count}\n")


# ============================================================================
# ФУНКЦИИ ДЛЯ ФИЛЬТРАЦИИ И ОЧИСТКИ
# ============================================================================

def filter_by_language(input_file: Path, output_file: Path) -> Tuple[int, int]:
    """
    Фильтрует предложения по языку (определяет, итальянские ли они)
    Возвращает количество оставшихся и отброшенных предложений
    """
    print("Начало фильтрации по языку...")

    ca_count = 0
    non_ca_count = 0

    with open(input_file, 'r', encoding='utf-8') as infile, \
            open(output_file, 'w', encoding='utf-8') as outfile, \
            open(LANGUAGE_LOG, 'w', encoding='utf-8') as logfile:

        lines = [line.strip() for line in infile if line.strip()]
        total_lines = len(lines)

        # Проверяем только часть предложений для скорости
        check_lines = lines[:min(LANGUAGE_CHECK_SAMPLE_SIZE, total_lines)] if ENABLE_LANGUAGE_CHECK else lines

        for i, line in enumerate(check_lines):
            try:
                lang = detect(line)
                if lang == 'it':  # итальянский
                    outfile.write(line + '\n')
                    ca_count += 1
                else:
                    logfile.write(f"{i + 1}: [{lang}] {line}\n")
                    non_ca_count += 1
            except LangDetectException:
                logfile.write(f"{i + 1}: [UNKNOWN] {line}\n")
                non_ca_count += 1

            if (i + 1) % 1000 == 0:
                print(f"Проверено языков: {i + 1}/{len(check_lines)}")

        # Если проверяли только часть, добавляем остальные без проверки
        if ENABLE_LANGUAGE_CHECK and total_lines > LANGUAGE_CHECK_SAMPLE_SIZE:
            for i in range(LANGUAGE_CHECK_SAMPLE_SIZE, total_lines):
                outfile.write(lines[i] + '\n')
                ca_count += 1

    print(f"Фильтрация завершена. Итальянских: {ca_count}, других: {non_ca_count}")
    return ca_count, non_ca_count


def final_cleanup(input_file: Path, output_file: Path) -> Dict[str, int]:
    """
    Финальная очистка предложений с проверкой на CAPS и другие проблемы
    Возвращает статистику очистки
    """
    print("Начало финальной очистки...")

    stats = {
        'accepted': 0,
        'too_many_caps': 0,
        'html_tags': 0,
        'url_email': 0,
        'chapter_markers': 0,
        'dates': 0,
        'repeats': 0,
        'no_punctuation': 0,
    }

    seen_sentences = set()

    with open(input_file, 'r', encoding='utf-8') as infile, \
            open(output_file, 'w', encoding='utf-8') as outfile, \
            open(CLEANING_LOG, 'w', encoding='utf-8') as logfile:

        for i, line in enumerate(infile, 1):
            original = line.strip()
            if not original:
                continue

            # 1. Проверка на много заглавных букв (возможно, аббревиатура)
            caps_words = re.findall(r'\b[A-ZÀ-ÿ]{3,}\b', original)
            if len(caps_words) > 3:  # более 3 слов в верхнем регистре
                logfile.write(f"{i}: МНОГО ЗАГЛАВНЫХ ({len(caps_words)}): {original[:100]}...\n")
                stats['too_many_caps'] += 1
                continue

            # 2. Проверка HTML/разметки
            if re.search(r'<[^>]+>|&[a-z]+;', original):
                logfile.write(f"{i}: HTML/РАЗМЕТКА: {original[:100]}...\n")
                stats['html_tags'] += 1
                continue

            # 3. Проверка на номер главы
            if re.match(r'^(CAPITOLO|Capitolo)\s+\d+', original, re.IGNORECASE):
                logfile.write(f"{i}: НОМЕР ГЛАВЫ: {original}\n")
                stats['chapter_markers'] += 1
                continue

            # 4. Проверка на даты
            if re.search(r'\d+\s+(di|del|dell[oa])\s+[a-z]+\s+(di\s+)?\d{4}', original, re.IGNORECASE):
                logfile.write(f"{i}: ДАТА: {original}\n")
                stats['dates'] += 1
                continue

            # 5. Проверка URL/email
            if re.search(r'https?://|www\.|\S+@\S+\.\S+', original):
                logfile.write(f"{i}: URL/EMAIL: {original[:100]}...\n")
                stats['url_email'] += 1
                continue

            # 6. Проверка повторов
            normalized = original.lower().strip('.,;!?¿¡')
            if normalized in seen_sentences:
                logfile.write(f"{i}: ПОВТОР: {original[:100]}...\n")
                stats['repeats'] += 1
                continue
            seen_sentences.add(normalized)

            # 7. Проверка пунктуации
            if not re.search(r'[.!?…]$', original):
                cleaned = original + '.'
                logfile.write(f"{i}: ДОБАВЛЕНА ТОЧКА: {original[:100]}...\n")
                stats['no_punctuation'] += 1
                outfile.write(cleaned + '\n')
            else:
                outfile.write(original + '\n')

            stats['accepted'] += 1

            if i % 1000 == 0:
                print(f"Очищено: {i} предложений")

    print(f"Очистка завершена. Принято: {stats['accepted']}")
    return stats


# ============================================================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================================================

def main():
    """Основная функция для запуска парсера"""

    # Создаём директории
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Находим все книги
    books = list(BOOKS_DIR.glob('*.txt'))

    if not books:
        print(f"В директории {BOOKS_DIR} не найдено книг!")
        print(f"\nПоместите книги в формате .txt в папку: {BOOKS_DIR}")
        return

    print(f"Найдено {len(books)} книг для обработки:")
    for book in books:
        print(f"  - {book.name}")

    # 1. Первичный парсинг книг
    print("\n" + "=" * 60)
    print("ЭТАП 1: Парсинг книг и извлечение предложений")
    print("=" * 60)

    parser = ItalianBookParser()
    parser.process_all_books(books)

    # Проверяем, достаточно ли предложений
    if parser.stats['valid_sentences'] < 13000:
        print(f"\nВНИМАНИЕ: Получено только {parser.stats['valid_sentences']} предложений.")
        print("Нужно 13000. Возможно, потребуется добавить больше книг.")

    # 2. Фильтрация по языку (если включена)
    if ENABLE_LANGUAGE_CHECK and OUTPUT_FILE.exists():
        print("\n" + "=" * 60)
        print("ЭТАП 2: Фильтрация по языку (итальянский)")
        print("=" * 60)

        italian_count, other_count = filter_by_language(OUTPUT_FILE, FILTERED_FILE)
        print(f"Итальянских предложений: {italian_count}")
        print(f"Других языков: {other_count}")

        input_file_for_cleanup = FILTERED_FILE
    else:
        input_file_for_cleanup = OUTPUT_FILE

    # 3. Финальная очистка
    print("\n" + "=" * 60)
    print("ЭТАП 3: Финальная очистка и проверка")
    print("=" * 60)

    if input_file_for_cleanup.exists():
        cleaning_stats = final_cleanup(input_file_for_cleanup, CLEANED_FILE)

        print("\nСтатистика очистки:")
        for key, value in cleaning_stats.items():
            print(f"  {key}: {value}")

        # Проверяем итоговое количество
        with open(CLEANED_FILE, 'r', encoding='utf-8') as f:
            final_count = sum(1 for _ in f)

        print(f"\nИтоговое количество предложений: {final_count}")

        if final_count >= 13000:
            print(f"\n✓ ЗАДАНИЕ ВЫПОЛНЕНО! Получено {final_count} предложений.")
            print(f"Файл для использования: {CLEANED_FILE}")
        else:
            print(f"\n✗ Не хватает {13000 - final_count} предложений.")
            print("Нужно добавить больше книг или ослабить критерии фильтрации.")

        # Показываем примеры предложений
        print("\n" + "=" * 60)
        print("ПРИМЕРЫ ИЗВЛЕЧЁННЫХ ПРЕДЛОЖЕНИЙ:")
        print("=" * 60)

        try:
            with open(CLEANED_FILE, 'r', encoding='utf-8') as f:
                lines = [line.strip() for line in f if line.strip()]

            if lines:
                for i in range(min(5, len(lines))):
                    print(f"{i + 1}. {lines[i]}")
        except Exception as e:
            print(f"Ошибка при чтении финального файла: {e}")
    else:
        print(f"Файл для очистки не найден: {input_file_for_cleanup}")


if __name__ == "__main__":
    main()