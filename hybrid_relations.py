"""
Hybrid Relations Extraction Module
Комбинирует rule-based подход и LLM для максимального покрытия.
"""
import logging
from typing import List, Dict, Tuple
from relations import extract_relations as extract_relations_regex
from llm_relations import extract_relations_llm

logger = logging.getLogger(__name__)


def extract_relations(text: str, entities: List[Dict] = None) -> List[Tuple]:
    """
    Гибридное извлечение связей:
    1. Сначала быстрые регулярки (relations.py)
    2. Затем LLM для сложных случаев (llm_relations.py)
    3. Объединяем результаты, убираем дубликаты
    
    Args:
        text: Исходный текст
        entities: Список сущностей [{"type": "per", "text": "Иван"}, ...]
    
    Returns:
        Список кортежей (subject, relation, object) для графовой БД
    """
    if entities is None:
        entities = []
    
    # Шаг 1: Регулярки (быстро, шаблонно)
    regex_relations = extract_relations_regex(text, entities)
    logger.info(f"Regex нашёл {len(regex_relations)} связей")
    
    # Шаг 2: LLM (медленнее, но умнее) — запускаем всегда для полноты
    llm_relations = extract_relations_llm(text, entities)
    logger.info(f"LLM нашёл {len(llm_relations)} связей")
    
    # Шаг 3: Объединяем с дедупликацией
    all_relations = list(regex_relations)  # начинаем с регулярок
    
    # Пары (субъект, объект) которые уже есть
    existing_pairs = {(r[0], r[2]) for r in regex_relations}
    
    # Добавляем LLM-связи, которые ещё не встречались
    for rel in llm_relations:
        pair = (rel[0], rel[2])
        if pair not in existing_pairs:
            all_relations.append(rel)
            existing_pairs.add(pair)
    
    logger.info(f"Всего после объединения: {len(all_relations)} связей")
    return all_relations