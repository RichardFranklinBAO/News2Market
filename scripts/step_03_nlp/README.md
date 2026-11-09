# Step 3 — Financial NLP

- `lm_dictionary.py`: validate and load the externally supplied official Loughran–McDonald financial dictionary.
- `lm_sentiment.py`: produce transparent dictionary-frequency/polarity features.
- `event_tagging.py`: optional, preliminary rule-based topic tags (not validated event labels).
- `local_llm_labels.py`: optional experimental locally installed Ollama audit; **not** part of the mandatory unified runner and not a validated model.

The modern unified pipeline also uses `src/news2market/research/metrics.py` for source-aware LM features and text-quality safeguards.
