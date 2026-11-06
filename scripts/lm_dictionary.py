"""Official Loughran–McDonald Master Dictionary CSV loader and auditable word-count scorer.

Source: https://sraf.nd.edu/loughranmcdonald-master-dictionary/
The full academic-research lexicon is NOT bundled or redistributable here; install from source.
Version pinned by filename (1993–2025; Notre Dame page updated March 2026),
AND the actual file's SHA256 hash is logged on each run.
"""
from __future__ import annotations

import csv
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

from common import INPUTS

LM_FILENAME = 'Loughran-McDonald_MasterDictionary_1993-2025.csv'
LM_SOURCE = 'https://sraf.nd.edu/loughranmcdonald-master-dictionary/'
LM_VERSION = 'MasterDictionary 1993-2025 (Notre Dame page updated 2026-03)'
CATEGORIES = ('Negative','Positive','Uncertainty','Litigious','Strong_Modal','Weak_Modal','Constraining')
TOKEN_RE = re.compile(r'[A-Za-z]{2,}')


def canonical(name: str) -> str:
    return re.sub(r'[^a-z0-9]', '', name.strip().lower().lstrip('\ufeff'))


def is_active_flag(value: str) -> bool:
    """LM uses a POSITIVE year for active terms, zero for absent, negative for removed."""
    try:
        return float(str(value).strip()) > 0.0
    except (TypeError, ValueError):
        raise ValueError(f'Unrecognized LM category flag: {value!r}') from None


@dataclass
class Lexicon:
    categories: dict[str, frozenset[str]]
    source_path: str
    sha256: str
    file_words: int

    def score(self, title: str, body: str, char_cap: int = 30000) -> dict:
        # Include the title once and up to char_cap body characters. No substring matching.
        words = [match.group().upper() for match in TOKEN_RE.finditer((title or '')+'\n'+(body or '')[:char_cap])]
        frequencies = Counter(words)
        total = len(words)
        matches = {name: Counter({w: count for w,count in frequencies.items() if w in entries})
                   for name,entries in self.categories.items()}
        counts = {name: sum(words.values()) for name,words in matches.items()}
        pos, neg = counts['Positive'], counts['Negative']
        denom = pos+neg
        score = (pos-neg)/denom if denom else 0.0
        # Zero matches is a neutral-coded MISSING SIGNAL, not evidence of neutral fundamentals.
        result = {
            'score': round(score,6),
            'sentiment': 'positive' if score>0.15 else ('negative' if score < -0.15 else 'neutral'),
            'lm_token_count': total,
            'lm_polarity_hits': denom,
            'lm_no_polarity_hits': denom==0,
            'lm_coverage_count': sum(count for w,count in frequencies.items()
                                     if any(w in entries for entries in self.categories.values())),
            'lm_text_truncated': len(body or '')>char_cap,
        }
        for category in CATEGORIES:
            k=category.lower()
            result[f'lm_{k}_count']=counts[category]
            result[f'lm_{k}_per_1000']=round(1000*counts[category]/total,6) if total else 0.0
        for category in ('Positive','Negative','Uncertainty'):
            # Terms + frequencies support human audits; no arbitrary hand-picked word list.
            result[f'lm_{category.lower()}_matched']= '; '.join(
                f'{word.lower()}:{n}' for word,n in sorted(matches[category].items()))
        return result


def load_lm_dictionary(path: Path | None = None, min_entries: int = 1000) -> Lexicon:
    path = Path(path) if path else INPUTS / LM_FILENAME
    if not path.exists():
        raise FileNotFoundError(
            f'Missing official LM dictionary: {path}. '
            f'Download the official CSV from {LM_SOURCE}. '
            'The full dictionary is NOT bundled, and demo is NOT an LM substitute.')
    raw = path.read_bytes()
    digest = sha256(raw).hexdigest()
    categories: dict[str,set[str]]={key:set() for key in CATEGORIES}
    terms_seen: set[str] = set()
    try:
        with path.open('r', encoding='utf-8-sig', newline='') as f:
            reader=csv.DictReader(f)
            if not reader.fieldnames:
                raise ValueError('CSV has no header.')
            columns={canonical(name):name for name in reader.fieldnames}
            expected=['word']+[canonical(x) for x in CATEGORIES]
            missing=[name for name in expected if name not in columns]
            if missing:
                raise ValueError(f'Official LM CSV missing required columns {missing}. Headers: {reader.fieldnames[:25]}')
            for row in reader:
                word=str(row.get(columns['word'], '')).strip().upper()
                if not word or not TOKEN_RE.fullmatch(word):
                    continue
                terms_seen.add(word)
                for name in CATEGORIES:
                    if is_active_flag(row.get(columns[canonical(name)], '')):
                        categories[name].add(word)
    except UnicodeError as e:
        raise ValueError('LM CSV encoding could not be read; please download the official CSV directly.') from e
    if len(terms_seen) < min_entries or (min_entries >= 1000 and (len(categories['Negative'])<100 or len(categories['Positive'])<100)):
        raise ValueError(
            f'LM lexicon appears incomplete ({len(terms_seen)} words, '
            f'{len(categories["Positive"])} positive, {len(categories["Negative"])} negative). '
            'Provide the COMPLETE official master CSV, not a sample or HTML login page.')
    return Lexicon({k:frozenset(v) for k,v in categories.items()}, str(path), digest,len(terms_seen))
