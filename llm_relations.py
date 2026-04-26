"""
LLM-based Relations Extraction Module
Semantic relation extractor using Groq API (Llama 3.1)
Заменяет/дополняет rule-based подход из relations.py
"""
import os
import json
import logging
from typing import List, Dict, Tuple
from openai import OpenAI
from dotenv import load_dotenv

# Явно указываем, где лежит .env
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
print(f"Ищу .env здесь: {dotenv_path}")
print(f"Файл существует: {os.path.exists(dotenv_path)}")
load_dotenv(dotenv_path)

load_dotenv()

logger = logging.getLogger(__name__)

# Инициализация клиента Groq
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ.get("GROQ_API_KEY")
)

# Промпт, заточенный под метрические книги
RELATION_PROMPT = """Ты — эксперт по анализу исторических документов (метрические книги Российской империи).
Найди ВСЕ смысловые связи между указанными сущностями в тексте.

Текст документа:
{text}

Найденные сущности:
{entities_json}

Определи связи между ними. Возможные типы отношений:
BORN_IN, BORN_ON, DIED_IN, DIED_ON, CHILD_OF, MARRIED_TO, GODPARENT_OF, 
LIVED_IN, WORKED_AS, OWNED_BY, LOCATED_IN

Верни ТОЛЬКО JSON-массив (ничего кроме JSON):
[{{"subject": "Имя субъекта", "relation": "ТИП_ОТНОШЕНИЯ", "object": "Имя объекта"}}]

Правила:
1. Используй ТОЛЬКО сущности из списка, не выдумывай новые
2. Если связей нет — верни []
3. Текст ответа — только JSON, без комментариев и пояснений
"""


def extract_relations_llm(text: str, entities: List[Dict]) -> List[Tuple]:
    """
    Извлекает связи между сущностями через LLM (Groq + Llama 3.1).
    
    Args:
        text: Исходный текст документа
        entities: Список сущностей [{"type": "per", "text": "Иван"}, ...]
    
    Returns:
        Список кортежей (subject, relation, object) — формат как в relations.py
    """
    if not entities or len(entities) < 2:
        logger.debug("Недостаточно сущностей для LLM")
        return []
    
    # Готовим сущности для промпта (убираем лишние поля)
    entities_for_prompt = [
        {"text": e["text"], "type": e["type"]} 
        for e in entities
    ]
    
    prompt = RELATION_PROMPT.format(
        text=text[:3000],  # обрезаем длинный текст для экономии токенов
        entities_json=json.dumps(entities_for_prompt, ensure_ascii=False, indent=2)
    )
    
    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",  # быстрая и бесплатная
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Убираем markdown-обёртки ```json ... ``` если есть
        if result_text.startswith("```"):
            lines = result_text.split("\n")
            lines = lines[1:-1]  # убираем первую и последнюю строку
            result_text = "\n".join(lines)
        
        llm_relations = json.loads(result_text)
        
        # Преобразуем в формат (subject, relation, object)
        triples = [
            (rel["subject"], rel["relation"], rel["object"])
            for rel in llm_relations
        ]
        
        logger.info(f"LLM нашёл {len(triples)} связей")
        return triples
        
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка парсинга JSON от LLM: {e}")
        logger.debug(f"Ответ: {result_text}")
        return []
    
    except Exception as e:
        logger.error(f"Ошибка LLM: {e}")
        return []