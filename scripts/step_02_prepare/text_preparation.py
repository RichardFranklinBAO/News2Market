"""Create LLM-ready text WITHOUT modifying raw evidence or original LM scores."""
from __future__ import annotations
import re
from scripts.shared.common import RESULTS,read_csv,write_csv,json_dump,message

NVIDIA_BOILERPLATE=re.compile(r"\bAbout\s+NVIDIA\b",re.IGNORECASE)

def trim_boilerplate(article):
    original=article.get('text','')
    cleaned=original
    reason='none'
    # Only apply a known site-specific heading, and never to arbitrary publishers.
    if article.get('source_type')=='first_party_press_release' and 'nvidianews.nvidia.com' in article.get('url',''):
        for hit in NVIDIA_BOILERPLATE.finditer(original):
            if hit.start() >= min(250,max(80,round(len(original)*0.15))):
                cleaned=original[:hit.start()].rstrip()
                reason='NVIDIA_about_company_footer'
                break
    return {**article,'raw_text_chars':len(original),'narrative_text':cleaned,
            'narrative_chars':len(cleaned),'boilerplate_removed_chars':len(original)-len(cleaned),
            'boilerplate_rule':reason}

def main():
    a=read_csv(RESULTS/'04_articles.csv')
    out=[trim_boilerplate(x) for x in a]
    write_csv(RESULTS/'11_nlp_ready_articles.csv',out)
    json_dump(RESULTS/'11_nlp_ready_audit.json',{'count':len(out),'footer_trimmed':sum(x['boilerplate_rule']!='none' for x in out),
      'total_chars_removed':sum(x['boilerplate_removed_chars'] for x in out),
      'caution':'Site-specific footers, heuristic. Raw text in 04_articles.csv is preserved. LM scores from 05 were computed on original text.'})
    message(f"LLM-ready text: {len(out)} documents; {sum(x['boilerplate_rule']!='none' for x in out)} known NVIDIA boilerplates trimmed.")

if __name__=='__main__':main()
