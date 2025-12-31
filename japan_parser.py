import re
import os
import hashlib
from collections import Counter
import time


def contains_latin_letters(text):
    """
    Проверяет, содержит ли текст латинские буквы (A-Z, a-z)
    включая одиночные буквы
    """
    # Регулярное выражение для любой латинской буквы
    return bool(re.search(r'[A-Za-z]', text))


def filter_out_latin(input_path, output_path):
    """
    Удаляет строки с любыми латинскими буквами
    """
    pure_japanese_lines = []
    removed_lines = []

    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            if contains_latin_letters(line):
                removed_lines.append((line_num, line))
            else:
                pure_japanese_lines.append(line)

    # Сохраняем чистые японские строки
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in pure_japanese_lines:
            f.write(f"{line}\n")

    # Сохраняем лог удалённых строк
    if removed_lines:
        log_path = output_path.replace('.txt', '_removed_latin.log')
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"Удалено строк с латинскими буквами: {len(removed_lines)}\n")
            f.write("=" * 60 + "\n")
            for line_num, text in removed_lines[:100]:  # Первые 100 примеров
                f.write(f"Строка {line_num}: {text}\n")

    print(f"Результаты фильтрации:")
    print(f"Исходно строк: {len(pure_japanese_lines) + len(removed_lines)}")
    print(f"Чистых японских строк (без латиницы): {len(pure_japanese_lines)}")
    print(f"Удалено строк с латиницей: {len(removed_lines)}")

    if removed_lines:
        print(f"\nПримеры удалённых строк:")
        for line_num, text in removed_lines[:5]:
            print(f"  Строка {line_num}: {text[:80]}...")

    return pure_japanese_lines


# ДОПОЛНИТЕЛЬНАЯ ФУНКЦИЯ: Удаление римских цифр (I, V, X, L, C, D, M)
def contains_roman_numerals(text):
    """
    Проверяет наличие римских цифр
    """
    return bool(re.search(r'\b[IVXLCDM]+\b', text, re.IGNORECASE))


def filter_strict_japanese(input_path, output_path):
    """
    Строгая фильтрация: удаляет строки с:
    1. Латинскими буквами (A-Z, a-z)
    2. Римскими цифрами
    3. Латинскими словами в кавычках (например "Protego")
    """
    pure_japanese_lines = []
    removed_by_latin = []
    removed_by_roman = []
    removed_by_quotes = []

    with open(input_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            # 1. Проверка на латинские буквы
            if re.search(r'[A-Za-z]', line):
                removed_by_latin.append((line_num, line))
                continue

            # 2. Проверка на римские цифры
            if re.search(r'\b[IVXLCDM]+\b', line, re.IGNORECASE):
                removed_by_roman.append((line_num, line))
                continue

            # 3. Проверка на латинские слова в кавычках (например “Protego”)
            # Ищем последовательности латинских букв в японских/английских кавычках
            if re.search(r'[「」『』"\'][A-Za-z]+[「」『』"\']', line):
                removed_by_quotes.append((line_num, line))
                continue

            pure_japanese_lines.append(line)

    # Сохраняем
    with open(output_path, 'w', encoding='utf-8') as f:
        for line in pure_japanese_lines:
            f.write(f"{line}\n")

    # Сохраняем детальный лог
    total_removed = len(removed_by_latin) + len(removed_by_roman) + len(removed_by_quotes)
    if total_removed > 0:
        log_path = output_path.replace('.txt', '_strict_filter.log')
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"ДЕТАЛЬНАЯ СТАТИСТИКА ФИЛЬТРАЦИИ\n")
            f.write("=" * 60 + "\n")
            f.write(f"Исходно строк: {len(pure_japanese_lines) + total_removed}\n")
            f.write(f"Сохранено строк: {len(pure_japanese_lines)}\n")
            f.write(f"Всего удалено: {total_removed}\n\n")

            f.write(f"Удалено по категориям:\n")
            f.write(f"  1. Латинские буквы: {len(removed_by_latin)}\n")
            f.write(f"  2. Римские цифры: {len(removed_by_roman)}\n")
            f.write(f"  3. Латинские слова в кавычках: {len(removed_by_quotes)}\n\n")

            if removed_by_latin:
                f.write("Примеры удалённых (латинские буквы):\n")
                for line_num, text in removed_by_latin[:10]:
                    f.write(f"  Строка {line_num}: {text}\n")
                f.write("\n")

            if removed_by_roman:
                f.write("Примеры удалённых (римские цифры):\n")
                for line_num, text in removed_by_roman[:5]:
                    f.write(f"  Строка {line_num}: {text}\n")
                f.write("\n")

            if removed_by_quotes:
                f.write("Примеры удалённых (слова в кавычках):\n")
                for line_num, text in removed_by_quotes[:5]:
                    f.write(f"  Строка {line_num}: {text}\n")

    print(f"\nСТРОГАЯ ФИЛЬТРАЦИЯ ЗАВЕРШЕНА:")
    print(f"Сохранено чистых японских строк: {len(pure_japanese_lines)}")
    print(f"Удалено: {total_removed} строк")
    print(f"  - Латинские буквы: {len(removed_by_latin)}")
    print(f"  - Римские цифры: {len(removed_by_roman)}")
    print(f"  - Слова в кавычках: {len(removed_by_quotes)}")

    return pure_japanese_lines


# БЫСТРЫЙ ВАРИАНТ: Если нужна только основная фильтрация
def quick_filter_japanese(input_path, output_path):
    """
    Быстрая фильтрация латиницы (основные проблемы из ваших примеров)
    """
    pattern = re.compile(r'[A-Za-z]')  # Любая латинская буква

    with open(input_path, 'r', encoding='utf-8') as f_in:
        lines = [line.strip() for line in f_in if line.strip()]

    filtered = [line for line in lines if not pattern.search(line)]

    # with open(output_path, 'w', encoding='utf-8') as f_out:
    #     for line in filtered:
    #         f_out.write(f"{line}\n")

    print(f"Быстрая фильтрация:")
    print(f"Исходно: {len(lines)} строк")
    print(f"После фильтрации: {len(filtered)} строк")
    print(f"Удалено: {len(lines) - len(filtered)} строк")

    return filtered

# ==============================
# ОСНОВНЫЕ ФУНКЦИИ ДЛЯ ЯПОНСКОГО
# ==============================

def clean_sentence_jp(sent):
    """
    Очистка японского предложения для TTS
    """
    if not sent or len(sent.strip()) == 0:
        return None

    # Убираем японские кавычки и скобки
    sent = re.sub(r'[「」『』《》【】〔〕]', '', sent)

    # Убираем обычные скобки и их содержимое
    sent = re.sub(r'\([^)]*\)', '', sent)
    sent = re.sub(r'\[[^\]]*\]', '', sent)

    # Убираем специальные символы (но сохраняем японскую пунктуацию)
    sent = re.sub(r'[#@$%&*_+=|~<>/\\\\]', '', sent)

    # Убираем римские цифры в начале (главы)
    sent = re.sub(r'^[IVXLCDMivxlcdm]+\.\s*', '', sent)

    # Убираем номера глав на японском (第X章, 第X話)
    sent = re.sub(r'^第\s*[零一二三四五六七八九十百千万\d]+\s*[章話節]\s*', '', sent)

    # Убираем лишние пробелы (в японском их почти нет, но на всякий случай)
    sent = ' '.join(sent.split())

    # Удаляем точки в середине (артефакты)
    sent = re.sub(r'(?<=[^\s])\.(?=[^\s])', '', sent)

    return sent.strip()


def count_japanese_words(text):
    """
    Приблизительный подсчёт слов в японском тексте.
    В японском нет пробелов, поэтому используем эвристику:
    - Иероглифы (кандзи) и катакана обычно обозначают слова
    - Хирагана часто является частью слов
    """
    # Разбиваем на "токены" по границам между типами символов
    # Это упрощённый подход, но для фильтрации по длине подойдёт
    tokens = []
    current_token = ""
    prev_type = None

    for char in text:
        # Определяем тип символа
        if '\u4e00' <= char <= '\u9fff':  # Кандзи (китайские иероглифы)
            char_type = "kanji"
        elif '\u30a0' <= char <= '\u30ff':  # Катакана
            char_type = "kana"
        elif '\u3040' <= char <= '\u309f':  # Хирагана
            char_type = "hiragana"
        elif char.isalpha():  # Латинские буквы
            char_type = "latin"
        elif char.isdigit():  # Цифры
            char_type = "digit"
        else:  # Пунктуация и прочее
            char_type = "other"

        # Если тип изменился, начинаем новый токен
        if prev_type and prev_type != char_type and current_token:
            tokens.append(current_token)
            current_token = char
        else:
            current_token += char

        prev_type = char_type

    if current_token:
        tokens.append(current_token)

    # Фильтруем: считаем только канжи, катакану и латиницу как "слова"
    word_like_tokens = [t for t in tokens if any(
        ('\u4e00' <= c <= '\u9fff' or  # канжи
         '\u30a0' <= c <= '\u30ff' or  # катакана
         c.isalpha()) for c in t
    )]

    return len(word_like_tokens)


def clean_and_split_sentences_jp(text):
    """
    Очищает японский текст и разбивает на предложения.
    """
    # 1. Удаляем метаданные (от начала до "目次" или "第１章")
    start_patterns = [r'目次', r'第\s*[１１1]\s*章', r'第一章']
    for pattern in start_patterns:
        match = re.search(pattern, text)
        if match:
            text = text[match.start():]
            break

    # 2. Удаляем сноски и примечания
    text = re.sub(r'訳者注.*', '', text, flags=re.DOTALL)
    text = re.sub(r'注\s*\d+.*', '', text)

    # 3. Заменяем многоточия и специальные символы для разделения
    text = text.replace('…', '.')
    text = text.replace('―', '-')

    # 4. Разбиваем на предложения (японские и обычные знаки препинания)
    # Японские: 。！？
    # Обычные: .!?
    sentence_endings = r'[。！？.!?]+'
    sentences = re.split(sentence_endings, text)

    # 5. Фильтруем и очищаем предложения
    valid_sentences = []
    for sent in sentences:
        sent = clean_sentence_jp(sent)
        if not sent:
            continue

        # Удаляем номера глав полностью
        sent = re.sub(r'第\s*[零一二三四五六七八九十百千万\d]+\s*[章話節]\s*', '', sent)

        # Пропускаем предложения с цифрами (по заданию)
        if re.search(r'[\d０-９]', sent):  # Обычные и японские цифры
            continue

        # Минимальная длина - 15 символов (в японском меньше слов)
        if len(sent) < 35:
            continue

        if len(sent) > 50:
            continue

        # Подсчёт слов для японского
        word_count = count_japanese_words(sent)
        if word_count < 10:  # Минимум 7 "слов" по заданию
            continue

        if word_count > 70:  # Максимум 70 "слов"
            continue

        # Проверяем, что начинается с японского или английского символа
        first_char = sent[0]
        is_japanese = ('\u3040' <= first_char <= '\u309f' or  # хирагана
                       '\u30a0' <= first_char <= '\u30ff' or  # катакана
                       '\u4e00' <= first_char <= '\u9fff')  # канжи
        is_english = ('A' <= first_char <= 'Z') or ('a' <= first_char <= 'z')

        if not (is_japanese or is_english):
            continue

        # Добавляем японскую точку в конце
        if not sent.endswith('。'):
            sent += '。'

        valid_sentences.append(sent)

    return valid_sentences


def process_all_books_jp(book_folder, output_folder, required_count=12000):
    """
    Обрабатывает все японские книги в папке.
    """
    os.makedirs(output_folder, exist_ok=True)

    all_sentences = []
    book_files = sorted([f for f in os.listdir(book_folder) if f.endswith('.txt')])

    print(f"Найдено {len(book_files)} японских книг для обработки")

    for book_file in book_files:
        book_path = os.path.join(book_folder, book_file)
        print(f"Обработка: {book_file}")

        try:
            with open(book_path, 'r', encoding='utf-8') as f:
                text = f.read()

            sentences = clean_and_split_sentences_jp(text)
            all_sentences.extend(sentences)

            print(f"  Извлечено: {len(sentences)} предложений")
            print(f"  Всего накоплено: {len(all_sentences)} предложений")


        except Exception as e:
            print(f"  Ошибка при обработке {book_file}: {e}")

    # Сохраняем все отпарсенные предложения
    parsed_path = os.path.join(output_folder, "japanese_start.txt")
    with open(parsed_path, 'w', encoding='utf-8') as f:
        for sent in all_sentences:
            f.write(f"{sent}\n")

    # print(f"\nСохранен файл со всеми предложениями: {parsed_path}")
    print(f"Всего предложений: {len(all_sentences)}")


    if len(all_sentences) < required_count:
        print(f"ВНИМАНИЕ: Недостаточно предложений! Нужно {required_count}, есть только {len(all_sentences)}")
        print("Добавьте больше книг или ослабьте критерии фильтрации.")

    return all_sentences[:]


# ==============================
# ФУНКЦИИ ПРОВЕРКИ ДУБЛИКАТОВ (из вашего кода)
# ==============================

def check_duplicates(file_path, output_report_path=None):
    """Проверяет файл на дубликаты предложений"""
    print(f"\nПроверка файла на дубликаты: {file_path}")

    with open(file_path, 'r', encoding='utf-8') as f:
        lines = [line.strip() for line in f if line.strip()]

    total_lines = len(lines)

    # Создаем хеши
    hashes = []
    for line in lines:
        normalized = ' '.join(line.split()).lower()
        line_hash = hashlib.md5(normalized.encode('utf-8')).hexdigest()
        hashes.append((line_hash, line))

    # Находим дубликаты
    hash_counter = Counter([h[0] for h in hashes])
    duplicate_hashes = {h: count for h, count in hash_counter.items() if count > 1}

    num_unique = len(set([h[0] for h in hashes]))
    duplicate_lines = sum([count - 1 for count in hash_counter.values() if count > 1])

    print(f"Всего строк: {total_lines}")
    print(f"Уникальных строк: {num_unique}")
    print(f"Дубликатов (с повторениями): {duplicate_lines}")
    print(f"Процент уникальности: {(num_unique / total_lines * 100):.2f}%")

    # if duplicate_hashes and output_report_path:
    #     with open(output_report_path, 'w', encoding='utf-8') as f:
    #         f.write(f"Дубликаты найдены: {len(duplicate_hashes)} уникальных предложений повторяются\n")
    #         for h, count in list(duplicate_hashes.items())[:20]:
    #             f.write(f"Повторений: {count}\n")
    #             # Найдем пример
    #             for line_hash, line_text in hashes:
    #                 if line_hash == h:
    #                     f.write(f"Пример: {line_text[:100]}...\n")
    #                     break
    #             f.write("-" * 50 + "\n")

    return {
        'total': total_lines,
        'unique': num_unique,
        'duplicate_lines': duplicate_lines
    }


def remove_duplicates(input_path, output_path):
    """Создает новый файл без дубликатов"""
    seen_hashes = set()
    unique_lines = []

    with open(input_path, 'r', encoding='utf-8') as f:
        for line in f:
            text = line.strip()
            if not text:
                continue

            normalized = ' '.join(text.split()).lower()
            line_hash = hashlib.md5(normalized.encode('utf-8')).hexdigest()

            if line_hash not in seen_hashes:
                seen_hashes.add(line_hash)
                unique_lines.append(text)

    with open(output_path, 'w', encoding='utf-8') as f:
        for line in unique_lines:
            f.write(f"{line}\n")

    removed = len(seen_hashes) - len(unique_lines)
    print(f"Удалено дубликатов: {removed}")
    print(f"Сохранено уникальных строк: {len(unique_lines)}")

    return len(unique_lines)


# ==============================
# ОСНОВНОЙ БЛОК
# ==============================

if __name__ == "__main__":
    # Настройки для японского
    BOOK_FOLDER = "book_japanese/processed_books"  # Папка с японскими книгами
    OUTPUT_FOLDER = "book_japanese/parsed_sentences"  # Куда сохранять

    # 1. Парсим книги
    print("=" * 60)
    print("НАЧАЛО ПАРСИНГА ЯПОНСКИХ КНИГ")
    print("=" * 60)

    sentences = process_all_books_jp(BOOK_FOLDER, OUTPUT_FOLDER)

    # 2. Проверяем на дубликаты
    final_file = os.path.join(OUTPUT_FOLDER, f"japanese_start.txt")
    stats = check_duplicates(final_file, os.path.join(OUTPUT_FOLDER, "duplicates_report.txt"))

    # 3. Если есть дубликаты, создаем очищенную версию
    if stats['duplicate_lines'] > 0:
        unique_file = os.path.join(OUTPUT_FOLDER, f"japanese_final_unique.txt")
        remove_duplicates(final_file, unique_file)

    # 4. Примеры для проверки
    # print("\n" + "=" * 60)
    # print("ПЕРВЫЕ 5 ПРЕДЛОЖЕНИЙ ДЛЯ ПРОВЕРКИ:")
    # print("=" * 60)
    # for i, sent in enumerate(sentences[:5]):
    #     print(f"{i + 1}: {sent}")

    # 5. Статистика по длине
    print("\n" + "=" * 60)
    print("СТАТИСТИКА ПО ДЛИНЕ ПРЕДЛОЖЕНИЙ:")
    print("=" * 60)

    if sentences:
        lengths = [count_japanese_words(s) for s in sentences[:1000]]
        print(f"Среднее количество 'слов': {sum(lengths) / len(lengths):.1f}")
        print(f"Минимальное количество 'слов': {min(lengths)}")
        print(f"Максимальное количество 'слов': {max(lengths)}")
        # print(f"Предложений с более 70 'слов': {len([l for l in lengths if l > 70])}")

        # Проверка символов
        char_lengths = [len(s) for s in sentences[:1000]]
        print(f"\nСредняя длина в символах: {sum(char_lengths) / len(char_lengths):.1f}")
        print(f"Мин. символов: {min(char_lengths)}")
        print(f"Макс. символов: {max(char_lengths)}")

    print("\n" + "=" * 60)
    print("ПАРСИНГ ЗАВЕРШЕН!")
    print("=" * 60)

    input_file = "book_japanese/parsed_sentences/japanese_final_unique.txt"

    # Вариант 1: Быстрая фильтрация
    output_file1 = "book_japanese/parsed_sentences/japanese_no_latin.txt"
    print("=" * 60)
    print("БЫСТРАЯ ФИЛЬТРАЦИЯ (удаление латинских букв)")
    print("=" * 60)
    filtered1 = quick_filter_japanese(input_file, output_file1)

    # Вариант 2: Строгая фильтрация
    output_file2 = "book_japanese/parsed_sentences/japanese_pure_strict.txt"
    print("\n" + "=" * 60)
    print("СТРОГАЯ ФИЛЬТРАЦИЯ")
    print("=" * 60)
    filtered2 = filter_strict_japanese(input_file, output_file2)

    # Вывод примеров
    # print("\n" + "=" * 60)
    # print("ПЕРВЫЕ 10 ОТФИЛЬТРОВАННЫХ ПРЕДЛОЖЕНИЙ:")
    # print("=" * 60)
    # for i, sent in enumerate(filtered2[:10]):
    #     print(f"{i + 1}: {sent}")

    # Проверка что не осталось латиницы
    print("\n" + "=" * 60)
    print("ПРОВЕРКА НА НАЛИЧИЕ ЛАТИНИЦЫ:")
    print("=" * 60)

    latin_found = False
    for i, sent in enumerate(filtered2[:100]):  # Проверяем первые 100
        if re.search(r'[A-Za-z]', sent):
            print(f"НАЙДЕНО в строке {i + 1}: {sent[:50]}...")
            latin_found = True

    if not latin_found:
        print("✓ Латинских букв не обнаружено!")