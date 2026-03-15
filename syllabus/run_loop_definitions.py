import requests
import json
import time
import os
import re

# Configuration
API_URL = "http://localhost:11434/api/generate"
MODEL = "gemma:2b"
INPUT_FILE = "subjects.json"
OUTPUT_FILE = "ai_definitions.json"
DELAY = 1  # seconds between requests

# Load syllabus JSON
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    syllabus_data = json.load(f)

# Ensure we use a list of subjects
subjects = syllabus_data if isinstance(syllabus_data, list) else [syllabus_data]

# Normalize subject structure
for subject in subjects:
    for chapter in subject.get("chapters", []):
        normalized_topics = []
        for t in chapter.get("topics", []):
            if isinstance(t, str):
                normalized_topics.append({"topic": t})
            elif isinstance(t, dict):
                normalized_topics.append(t)
        chapter["topics"] = normalized_topics


def clean_response_text(text, topic=None):
    if not text:
        return ""

    raw = text.strip()
    out = raw.replace('```json', '').replace('```', '').strip()

    # Remove simple leading phrases from prompt without regex.
    lower_out = out.lower()
    prefixes = [
        "sure, here's a concise definition for you:",
        "sure here's a concise definition for you:",
        "sure, here is a concise definition for you:",
        "sure here is a concise definition for you:",
        "here's the definition of",
        "here is the definition of",
        "a concise definition for you:",
        "a concise definition is:",
        "definition:",
        "definition -",
        "please define",
        "please provide a definition of"
    ]
    for prefix in prefixes:
        if lower_out.startswith(prefix):
            out = out[len(prefix):].strip()
            lower_out = out.lower()
            break

    # If still starts with 'sure' or 'here', trim up to first sentence or colon.
    if lower_out.startswith('sure') or lower_out.startswith("here"):
        idx_colon = out.find(':')
        if idx_colon >= 0 and idx_colon < 120:
            out = out[idx_colon + 1:].strip()
            lower_out = out.lower()
        elif '.' in out:
            idx_period = out.find('.')
            out = out[idx_period + 1:].strip() if idx_period >= 0 else out
            lower_out = out.lower()

    # Remove explicit subject/chapter metadata using simple keyword ops (no regex).
    for token in ['subject:', 'chapter:']:
        idx = lower_out.find(token)
        while idx != -1:
            end = lower_out.find('.', idx)
            if end == -1:
                end = len(out)
            out = (out[:idx] + out[end + 1:]).strip()
            lower_out = out.lower()
            idx = lower_out.find(token)

    # Collapse line breaks and spaces but preserve paragraph breaks
    out = out.replace('\r', '')
    out = re.sub(r'\n\s*\n', '\n\n', out)  # keep paragraph separations
    out = re.sub(r'[ \t]+', ' ', out)            # normalize intra-line spaces
    out = re.sub(r'\n\s+', '\n', out)          # trim spaces after newline

    # If trimmed output is empty, fallback to raw sentence extraction
    if not out:
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', raw) if s.strip()]
        if topic:
            for s in sentences:
                if topic.lower() in s.lower():
                    out = s
                    break
        if not out and sentences:
            out = sentences[0]

    out = out.strip(' .')
    return out

def generate_definition(subject, chapter, topic):
    prompt = (
        f"Provide a detailed, formal explanation of the topic '{topic}' for students. "
        f"Subject: {subject}. Chapter: {chapter}. "
        "Use clear prose with at least 3 sentences, and include examples only as plain text explanations (no code). "
        "Avoid starting with 'Sure', 'Here's', or other meta commentary."
        "Produce varied wording each call so the response does not look repetitive."
    )

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.7,
        "top_p": 0.9,
        "max_tokens": 450
    }

    response = requests.post(API_URL, json=payload, timeout=300)
    response.raise_for_status()
    result = response.json()
    definition_text = result.get("response", "")
    return clean_response_text(definition_text, topic)


def save_output(data):
    # Write directly to ai_definitions.json without using a temporary file.
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# Build output structure with definitions only
output = []

for subject in subjects:
    subj_out = {
        "subject": subject.get("subject", ""),
        "year": subject.get("year", ""),
        "chapters": []
    }

    for chapter in subject.get("chapters", []):
        chap_out = {
            "chapter": chapter.get("chapter", ""),
            "topics": []
        }

        for t in chapter.get("topics", []):
            topic_name = t.get("topic") if isinstance(t, dict) else None
            if not topic_name:
                continue

            print(f"[GENERATING] {subj_out['subject']} > {chap_out['chapter']} > {topic_name}")
            try:
                definition = generate_definition(subj_out["subject"], chap_out["chapter"], topic_name)
            except Exception as e:
                print(f"[ERROR] {topic_name}: {e}")
                definition = ""
            definition = clean_response_text(definition, topic_name)

            chap_out["topics"].append({
                "topic": topic_name,
                "definition": definition
            })

            time.sleep(DELAY)

        subj_out["chapters"].append(chap_out)
    output.append(subj_out)

save_output(output)
print(f"Definitions written to {OUTPUT_FILE}")
