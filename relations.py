"""
Relations Extraction Module
Rule-based extractor optimized for historical metric books.
"""
import re
from typing import List, Dict, Tuple


def _extract_relations_from_sentence(sentence: str, sentence_entities: List[Dict]) -> List[Tuple]:
    """
    Извлекает тройки (субъект, отношение, объект) из одного предложения
    на основе ключевых маркеров и порядка сущностей.
    """
    triples = []
    lower_s = sentence.lower()
    
    pers = [e for e in sentence_entities if e['type'] in ('per', 'person')]
    locs = [e for e in sentence_entities if e['type'] in ('loc', 'location')]
    dates = [e for e in sentence_entities if e['type'] == 'date']

    # 1. Рождение/Крещение -> Место
    if re.search(r'родил[сяась]|рожд[енена]|крещ[енена]', lower_s):
        if pers and locs:
            triples.append((pers[0]['text'], 'BORN_IN', locs[0]['text']))
        if pers and dates:
            triples.append((pers[0]['text'], 'BORN_ON', dates[0]['text']))

    # 2. Родство: сын/дочь/ребёнок ... (у/при) ...
    if re.search(r'(сын|дочь|ребенок|дитя)\b', lower_s):
        if len(pers) >= 2:
            # В метрических книгах обычно: "родился сын Иван у мещанина Петра"
            triples.append((pers[0]['text'], 'CHILD_OF', pers[-1]['text']))

    # 3. Венчание/Брак
    if re.search(r'венчан[ыа]|сочетал[сяась]|вступил[а]? в брак', lower_s):
        if len(pers) >= 2:
            triples.append((pers[0]['text'], 'MARRIED_TO', pers[1]['text']))

    # 4. Крёстные/Восприемники
    if re.search(r'восприемник|восприемница|кум|кума|крестн[ыйая]', lower_s):
        if len(pers) >= 2:
            triples.append((pers[0]['text'], 'GODPARENT_OF', pers[1]['text']))

    # 5. Смерть
    if re.search(r'умер|скончался|помер', lower_s):
        if pers and dates:
            triples.append((pers[0]['text'], 'DIED_ON', dates[0]['text']))
        if pers and locs:
            triples.append((pers[0]['text'], 'DIED_IN', locs[0]['text']))

    return triples


def extract_relations(text: str, entities: List[Dict] = None) -> List[Tuple]:
    """
    Основной интерфейс пайплайна.
    Принимает текст и список структурированных сущностей.
    Возвращает список кортежей (субъект, отношение, объект).
    """
    if entities is None:
        entities = []

    # Разбиваем текст на предложения (учитываем русскую пунктуацию)
    sentences = re.split(r'(?<=[.!?;])\s+', text)
    
    all_relations = []
    
    for sent in sentences:
        # Находим сущности, попадающие в текущее предложение
        # Для MVP используем безопасное сравнение по подстроке
        sent_clean = re.sub(r'[^\w\sа-яёА-ЯЁ]', '', sent).lower()
        sent_entities = [
            e for e in entities 
            if re.sub(r'[^\w\s]', '', e['text']).lower() in sent_clean
        ]
        
        # Работаем только если в предложении ≥2 сущности (избегаем шума)
        if len(sent_entities) >= 2:
            relations = _extract_relations_from_sentence(sent, sent_entities)
            all_relations.extend(relations)

    # Убираем дубликаты, сохраняя порядок
    seen = set()
    unique_relations = []
    for rel in all_relations:
        key = (rel[0], rel[1], rel[2])
        if key not in seen:
            seen.add(key)
            unique_relations.append(rel)
            
    return unique_relations