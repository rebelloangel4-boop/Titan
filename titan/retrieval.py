"""Bounded lexical relevance ranking; no embeddings or external inference."""
import math
import re
from collections import Counter

STOP_WORDS = frozenset('a an and are as at be by for from how i in is it me of on or our the this to we what with you'.split())

def tokens(text):
    return [t for t in re.findall(r'[^\W_]+', text.casefold(), re.UNICODE) if t not in STOP_WORDS]

def rank(records, query, limit=8, max_chars=12000):
    terms = set(tokens(query))
    if not terms:
        return []
    documents = [(r, Counter(tokens(r['key'] + ' ' + r['key'] + ' ' + r['value']))) for r in records]
    if not documents:
        return []
    average = sum(sum(counts.values()) for _, counts in documents) / len(documents) or 1
    frequency = {term: sum(term in counts for _, counts in documents) for term in terms}
    scored = []
    for record, counts in documents:
        length = sum(counts.values())
        score = 0.0
        for term in terms:
            count = counts[term]
            if count:
                inverse = math.log(1 + (len(documents) - frequency[term] + 0.5) / (frequency[term] + 0.5))
                score += inverse * count * 2.2 / (count + 1.2 * (0.25 + 0.75 * length / average))
        if score:
            scored.append((score, record))
    scored.sort(key=lambda pair: (-pair[0], -pair[1]['updated'], pair[1]['key']))
    result = []
    for score, record in scored[:limit]:
        remaining = max_chars - sum(len(r['key']) + len(r['value']) for r in result)
        if remaining <= len(record['key']):
            break
        value = record['value'][:remaining - len(record['key'])]
        result.append({**record, 'value': value, 'score': round(score, 6),
                       'truncated': len(value) != len(record['value']), 'retrieval': 'lexical_bm25'})
    return result
