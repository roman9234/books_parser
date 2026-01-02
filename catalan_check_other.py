import re
from collections import Counter

input_file = "filtered_ca.txt"
output_file = "book_catalan/parsed_sentences/catalan_cleaned_all.txt"
log_file = "cleaning_log.txt"


def count_words(text):
    # Простой подсчёт слов для каталонского
    return len(re.findall(r'[a-zA-ZÀ-ÿ]+', text))


with open(input_file, 'r', encoding='utf-8') as infile, \
        open(output_file, 'w', encoding='utf-8') as outfile, \
        open(log_file, 'w', encoding='utf-8') as logfile:
    stats = Counter()
    seen_sentences = set()

    for i, line in enumerate(infile, 1):
        original = line.strip()
        if not original:
            continue

        # 1. Проверка длины
        word_count = count_words(original)
        if word_count < 7:
            logfile.write(f"{i}: СЛИШКОМ КОРОТКОЕ ({word_count} слов): {original}\n")
            stats['short'] += 1
            continue
        if word_count > 70:
            logfile.write(f"{i}: СЛИШКОМ ДЛИННОЕ ({word_count} слов): {original[:50]}...\n")
            stats['long'] += 1
            continue

        # 2. Проверка HTML/разметки
        if re.search(r'<[^>]+>|&[a-z]+;', original):
            logfile.write(f"{i}: HTML/РАЗМЕТКА: {original}\n")
            stats['html'] += 1
            continue

        # 3. Проверка на номер главы/даты (начало строки)
        if re.match(r'^(CAP[ÍI]TOL|Cap[íi]tol|CAP[ÍI]TLE|Cap[íi]tle)\s+\d+', original, re.IGNORECASE):
            logfile.write(f"{i}: НОМЕР ГЛАВЫ: {original}\n")
            stats['chapter'] += 1
            continue

        # 4. Проверка на даты (15 de març de 2024)
        if re.search(r'\d+\s+(de|d\')\s+[a-zç]+\s+(de\s+)?\d{4}', original, re.IGNORECASE):
            logfile.write(f"{i}: ДАТА: {original}\n")
            stats['date'] += 1
            continue

        # 5. Проверка URL/email
        if re.search(r'https?://|www\.|\S+@\S+\.\S+', original):
            logfile.write(f"{i}: URL/EMAIL: {original}\n")
            stats['url'] += 1
            continue

        # 6. Проверка на цифры (если хотим исключить)
        if re.search(r'\b\d+\b', original):
            logfile.write(f"{i}: ЦИФРЫ В ТЕКСТЕ: {original}\n")
            stats['digits'] += 1
            # continue  # раскомментировать, если нужно исключить

        # 7. Проверка повторов
        normalized = original.lower().strip('.,;!?¿¡')
        if normalized in seen_sentences:
            logfile.write(f"{i}: ПОВТОР: {original}\n")
            stats['repeat'] += 1
            continue
        seen_sentences.add(normalized)

        # 8. Проверка слишком много заглавных (возможно, аббревиатура)
        words = re.findall(r'[A-ZÀ-ÿ]{2,}', original)
        if len(words) > 3:  # более 3 слов в верхнем регистре
            logfile.write(f"{i}: МНОГО ЗАГЛАВНЫХ: {original}\n")
            stats['uppercase'] += 1

        # 9. Проверка пунктуации (отсутствие конечной пунктуации)
        if not re.search(r'[.!?¿¡…»]$', original):
            cleaned = original + '.'
            logfile.write(f"{i}: ДОБАВЛЕНА ТОЧКА: {original}\n")
            stats['punctuation'] += 1
            outfile.write(cleaned + '\n')
        else:
            outfile.write(original + '\n')

        stats['accepted'] += 1

        if i % 1000 == 0:
            print(f"Обработано: {i} строк")

print(f"\n=== СТАТИСТИКА ОЧИСТКИ ===")
for key, value in stats.items():
    print(f"{key}: {value}")

print(f"\nИтоговых предложений: {stats['accepted']}")
if stats['accepted'] < 12000:
    print(f"ВНИМАНИЕ: Не хватает {12000 - stats['accepted']} предложений!")