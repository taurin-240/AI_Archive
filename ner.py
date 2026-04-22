import os
import re
from navec import Navec
from slovnet import NER

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, 'models')

navec_path = os.path.join(MODELS_DIR, 'navec_news_v1_1B_250K_300d_100q.tar')
ner_model_path = os.path.join(MODELS_DIR, 'slovnet_ner_news_v1.tar')

navec = Navec.load(navec_path)
ner_model = NER.load(ner_model_path)
ner_model.navec(navec)


def translate_text(text: str) -> str:
    """
    Translates pre-revolutionary Russian text to post-revolutionary Russian.

    Args:
        text (str): Input text with pre-revolutionary characters.

    Returns:
        str: Translated text with modern Russian characters.

    Example:
        >>> translated = translate_text('Текст съ дореволюціонными буквами')
        >>> print(translated)
        'Некоторый текст с дореволюционными буквами'
    """
    replacements = {
        'ѣ': 'е',
        'Ѣ': 'Е',
        'i': 'и',
        'I': 'И',
        'І': 'И',
        'і': 'и',
        'ѵ': 'и',
        'Ѵ': 'И',
        'ѳ': 'ф',
        'Ѳ': 'Ф',
        "ћ": 'e',
        'y': 'ы'  # возможно, неправильно
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r'ъ(\s|[.,;:!?—–\n\"\'\)\]])', r'\1', text)
    text = re.sub(r'(\s|[.,;:!?—–\n\"\'(\[])ъ', r'\1', text)

    text = text.replace('ъ', '')
    text = text.replace('Ъ', '')

    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)

    return text.strip()


def find_dates(text: str) -> list:
    """
    Finds dates in various formats within a text.

    Args:
        text (str): Input text to search for dates.

    Returns:
        list: List of tuples (start_pos, end_pos, 'date') for each found date.

    Example:
        >>> dates = find_dates('Я родился 15.03.1990.')
        >>> print(dates)
        [(11, 21, 'date')]
    """
    date_pattern = r'\b(\d{1,2}[./\-]\d{1,2}[./\-]\d{4})\b'
    iso_pattern = r'\b(\d{4}-\d{2}-\d{2})\b'
    year_pattern = r'\b(\d{4})\s*(?:г\.?|год|года|году|годах)\b'
    year_decade_pattern = (r'\b(?:в\s+)?(\d{3}0)-[хxs]\s*'
                           r'(?:годах|годов|году|год|гг\.?)?\b')

    dates = []
    for match in re.finditer(date_pattern, text):
        dates.append((match.start(), match.end(), 'date'))
    for match in re.finditer(iso_pattern, text):
        dates.append((match.start(), match.end(), 'date'))
    for match in re.finditer(year_pattern, text):
        dates.append((match.start(), match.end(), 'date'))
    for match in re.finditer(year_decade_pattern, text):
        dates.append((match.start(), match.end(), 'date'))

    dates.sort(key=lambda x: x[0])
    return dates


def annotate_text(markup) -> str:
    """
    Annotates text with HTML mark tags based on NER and date spans.

    Args:
        markup: Slovnet markup object containing text and spans.

    Returns:
        str: Text with HTML mark tags for entities.

    Example:
        >>> annotated = annotate_text(markup)
        >>> print(annotated)
        'Привет <mark class="ner-per">Иван</mark>'
    """
    ner_spans = [
        (span.start, span.stop, span.type.lower()) for span in markup.spans]

    dates = find_dates(markup.text)

    all_spans = ner_spans + dates
    all_spans.sort(key=lambda x: x[0])

    tokens = []
    last = 0
    for start, stop, label in all_spans:
        if last < start:
            tokens.append(markup.text[last:start])
        entity_text = markup.text[start:stop]
        tokens.append(f'<mark class="ner-{label}">{entity_text}</mark>')
        last = stop
    if last < len(markup.text):
        tokens.append(markup.text[last:])
    return ''.join(tokens)


def perform_ner(text: str) -> str:
    """
    Performs NER on the input text and returns annotated HTML.

    Args:
        text (str): Input text to analyze.

    Returns:
        str: Annotated text with HTML mark tags for entities.

    Example:
        >>> annotated = perform_ner('Иван живет в Москве.')
        >>> print(annotated)
        '<mark class="ner-per">Иван</mark> живет в
        <mark class="ner-loc">Москве</mark>.'
    """
    markup = ner_model(text)
    return annotate_text(markup)


def extract_entities_structured(text: str) -> list[dict]:
    """
    Возвращает сущности в структурированном виде для пайплайна.
    Формат: [{"type": "PER", "text": "Иван Петров", "start": 0, "end": 12}, ...]
    """
    markup = ner_model(text)
    entities = []
    for span in markup.spans:
        entities.append({
            "type": span.type.lower(),
            "text": markup.text[span.start:span.stop],
            "start": span.start,
            "end": span.stop
        })
    # Добавляем даты из regex
    for start, end, _ in find_dates(text):
        entities.append({
            "type": "date",
            "text": text[start:end],
            "start": start,
            "end": end
        })
    # Сортируем по позиции, убираем пересечения (простая дедупликация)
    entities.sort(key=lambda x: x["start"])
    filtered = []
    last_end = 0
    for ent in entities:
        if ent["start"] >= last_end:
            filtered.append(ent)
            last_end = ent["end"]
    return filtered