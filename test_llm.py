"""
Тестирование LLM-модуля извлечения связей
"""
from llm_relations import extract_relations_llm
from relations import extract_relations

# Тестовый текст из метрической книги
test_text = """
1890 года мая 15 дня родился сын Иоанн у мещанина Петра Сидорова 
и законной жены его Анны. Восприемниками были купец Иван Кузнецов 
и девица Мария из Москвы.
"""

test_entities = [
    {"type": "per", "text": "Иоанн"},
    {"type": "per", "text": "Петр Сидоров"},
    {"type": "per", "text": "Анна"},
    {"type": "per", "text": "Иван Кузнецов"},
    {"type": "per", "text": "Мария"},
    {"type": "loc", "text": "Москва"},
    {"type": "date", "text": "1890 года мая 15 дня"}
]

print("=" * 50)
print("ТЕСТ: СРАВНЕНИЕ REGEX vs LLM")
print("=" * 50)
print(f"\nТекст: {test_text[:100]}...")
print(f"Сущностей: {len(test_entities)}")

# 1. Старый метод (регулярки)
print("\n--- REGEX (relations.py) ---")
regex_result = extract_relations(test_text, test_entities)
if regex_result:
    for s, r, o in regex_result:
        print(f"  {s} --[{r}]--> {o}")
else:
    print("  Связей не найдено")
print(f"  Всего: {len(regex_result)} связей")

# 2. Новый метод (LLM)
print("\n--- LLM (llm_relations.py) ---")
llm_result = extract_relations_llm(test_text, test_entities)
if llm_result:
    for s, r, o in llm_result:
        print(f"  {s} --[{r}]--> {o}")
else:
    print("  Связей не найдено")
print(f"  Всего: {len(llm_result)} связей")

# 3. Сравнение
print("\n--- РЕЗУЛЬТАТ ---")
regex_pairs = {(r[0], r[2]) for r in regex_result}
llm_pairs = {(r[0], r[2]) for r in llm_result}
only_llm = llm_pairs - regex_pairs
print(f"Regex нашёл: {len(regex_result)}")
print(f"LLM нашёл: {len(llm_result)}")
if only_llm:
    print(f"LLM нашёл дополнительно {len(only_llm)} связей, пропущенных regex:")
    for s, o in only_llm:
        print(f"  {s} <--> {o}")