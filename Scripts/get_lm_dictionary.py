"""One-time acquisition of official Notre Dame LM CSV for academic research.

No embedded word lists, no third-party mirror, no invented fallback.
The direct Drive ID originates in the official Notre Dame page (checked 2026-11-05).
"""
from __future__ import annotations
import argparse
from pathlib import Path
from common import INPUTS, message
from lm_dictionary import LM_FILENAME, LM_SOURCE, load_lm_dictionary

OFFICIAL_DRIVE_FILE_ID='1iq2RUf8qGFEAk1g8wQntP3habOnR3fXF'
OFFICIAL_DOWNLOAD_PAGE='https://drive.google.com/file/d/1iq2RUf8qGFEAk1g8wQntP3habOnR3fXF/view?usp=sharing'


def get_dictionary(destination: Path | None = None):
    dest = Path(destination) if destination else INPUTS / LM_FILENAME
    if dest.exists():
        lex=load_lm_dictionary(dest)
        message(f'Using existing verified LM master dictionary: {dest.name}, words={lex.file_words}, SHA256={lex.sha256}')
        return dest
    try:
        import gdown
    except ImportError as e:
        raise RuntimeError('Install requirements first: python -m pip install -r requirements.txt') from e
    dest.parent.mkdir(parents=True,exist_ok=True)
    temp=dest.with_name(dest.name+'.part')
    temp.unlink(missing_ok=True)
    message('Fetching Notre Dame official LM CSV from its public Google Drive link (academic research use).')
    try:
        downloaded = gdown.download(id=OFFICIAL_DRIVE_FILE_ID,output=str(temp),quiet=False)
        if not downloaded or not temp.exists():
            raise RuntimeError('Google Drive did not return a file (rate limiting or permissions).')
        lex=load_lm_dictionary(temp)
        temp.replace(dest)
        message(f'Official LM dictionary ready: {dest.name}; words={lex.file_words}; SHA256={lex.sha256}')
        return dest
    except Exception as exc:
        temp.unlink(missing_ok=True)
        raise RuntimeError(
            'Automatic dictionary download/validation failed. Download the official CSV manually from '
            f'{LM_SOURCE} (CSV → Google Drive), and save it to {dest} without renaming; '
            f'alternative direct page: {OFFICIAL_DOWNLOAD_PAGE}. Original error: {exc}') from exc


def main():
    parser=argparse.ArgumentParser(description='Download/verify official full LM dictionary (academic research).')
    parser.add_argument('--path',type=Path,default=None,help='Optional existing CSV to verify without downloading')
    args=parser.parse_args()
    get_dictionary(args.path)

if __name__=='__main__':
    main()
