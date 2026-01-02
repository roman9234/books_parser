from langdetect import detect, LangDetectException

input_file = "book_catalan/parsed_sentences/catalan_sentences_all.txt"
output_file = "filtered_ca.txt"
suspicious_file = "non_catalan_sentences.txt"

ca_count = 0
non_ca_count = 0

with open(input_file, 'r', encoding='utf-8') as infile, \
        open(output_file, 'w', encoding='utf-8') as outfile, \
        open(suspicious_file, 'w', encoding='utf-8') as suspfile:
    for line_num, line in enumerate(infile, 1):
        line = line.strip()
        if not line:
            continue

        try:
            lang = detect(line)
            if lang == 'ca':  # каталанский
                outfile.write(line + '\n')
                ca_count += 1
            else:
                suspfile.write(f"{line_num}: [{lang}] {line}\n")
                non_ca_count += 1
        except LangDetectException:
            # Если не удалось определить, считаем подозрительным
            suspfile.write(f"{line_num}: [UNKNOWN] {line}\n")
            non_ca_count += 1

        if line_num % 1000 == 0:
            print(f"Обработано: {line_num} строк")

print(f"\nСтатистика:")
print(f"Каталанских предложений: {ca_count}")
print(f"Не каталанских/ошибок: {non_ca_count}")
print(f"Сохранили в: {output_file}")
print(f"Подозрительные в: {suspicious_file}")

if ca_count < 12000:
    print(f"\nВНИМАНИЕ: Не хватает {12000 - ca_count} каталанских предложений!")