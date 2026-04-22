import re
from datetime import datetime

def normalize_date(date_str: str) -> str:
    """Приводит дату к формату YYYY-MM-DD."""
    # Убираем слова вроде 'года', 'г.', 'году'
    clean = re.sub(r'\s*(года|г\.|году|годах)\s*$', '', date_str.strip(), flags=re.IGNORECASE)
    
    # Пробуем распарсить DD.MM.YYYY или DD/MM/YYYY
    m = re.match(r'(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})', clean)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(year, month, day).strftime('%Y-%m-%d')
        except ValueError:
            pass
            
    # Если только год
    m = re.match(r'(\d{4})', clean)
    if m:
        return f"{m.group(1)}-01-01"
        
    return date_str  # Fallback

def normalize_name(name: str) -> str:
    """Очищает ФИО от титулов, приводит к Title Case."""
    # Убираем г., с., кр., восприемник, мещанин и т.п. в начале
    clean = re.sub(r'^(г\.\s+|с\.\s+|кр\.\s+|мещанин\s+|крестьянин\s+|дворянин\s+)', '', name.strip(), flags=re.IGNORECASE)
    # Убираем лишние пробелы, делаем Заглавными
    clean = re.sub(r'\s+', ' ', clean)
    return clean.title()

def normalize_location(loc: str) -> str:
    """Стандартизирует локации (убирает 'с.', 'г.', 'уезд')."""
    clean = re.sub(r'^(с\.\s+|г\.\s+|город\s+|село\s+|деревня\s+)', '', loc.strip(), flags=re.IGNORECASE)
    return clean.title()

def normalize_entity(entity: dict) -> dict:
    """Применяет нормализацию в зависимости от типа сущности."""
    text = entity['text']
    if entity['type'] == 'date':
        text = normalize_date(text)
    elif entity['type'] in ('per', 'person'):
        text = normalize_name(text)
    elif entity['type'] in ('loc', 'location'):
        text = normalize_location(text)
    return {**entity, 'text': text}