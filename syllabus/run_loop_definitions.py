import argparse
import requests
import json
import time
import os
import re

# Configuration
API_URL = "http://localhost:11434/api/generate"
MODEL = "gemma:2b"
INPUT_FILE = "class10syllabus.json"
OUTPUT_FILE = "class10syllabus-topic.json"
DELAY = 1  # seconds between requests

# Load syllabus JSON
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    syllabus_data = json.load(f)

# Ensure we use a list of subjects
subjects = syllabus_data if isinstance(syllabus_data, list) else [syllabus_data]

# Parse CLI arguments for resume/start options
parser = argparse.ArgumentParser(description='Generate AI definitions for topics.')
parser.add_argument('--start-subject', type=str, default=None, help='Subject name from which to start (inclusive)')
parser.add_argument('--start-chapter', type=str, default=None, help='Chapter name from which to start (inclusive)')
parser.add_argument('--start-topic', type=str, default=None, help='Topic name from which to start (inclusive)')
args = parser.parse_args()

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
    # Write in place to ai_definitions.json in full after each incremental update.
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def find_subject(out_list, subject_name, year_value):
    for item in out_list:
        if item.get("subject") == subject_name and item.get("year") == year_value:
            return item
    return None


def find_chapter(chapters_list, chapter_name):
    for item in chapters_list:
        if item.get("chapter") == chapter_name:
            return item
    return None


def find_topic(topics_list, topic_name):
    for item in topics_list:
        if item.get("topic") == topic_name:
            return item
    return None


# Build output structure with definitions only (resume from existing file if present)
output = []
if os.path.exists(OUTPUT_FILE):
    try:
        with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
            existing_output = json.load(f)
            if isinstance(existing_output, list):
                output = existing_output
    except Exception as e:
        print(f"[WARNING] Could not read existing output file: {e}")

subject_started = args.start_subject is None
chapter_started = args.start_chapter is None
topic_started = args.start_topic is None

total_topics = sum(len(c.get("topics", [])) for s in subjects for c in s.get("chapters", []))
current_topic = 0

for subject in subjects:
    subject_name = subject.get("subject", "")
    subject_year = subject.get("year", "")

    if not subject_started:
        if args.start_subject and subject_name == args.start_subject:
            subject_started = True
            # restart chapter/topic control when arriving at target subject
            chapter_started = args.start_chapter is None
            topic_started = args.start_topic is None
        else:
            current_topic += sum(len(c.get("topics", [])) for c in subject.get("chapters", []))
            continue

    subj_out = find_subject(output, subject_name, subject_year)
    if not subj_out:
        subj_out = {
            "subject": subject_name,
            "year": subject_year,
            "chapters": []
        }
        output.append(subj_out)

    # keep subject metadata current
    subj_out["subject"] = subject_name
    subj_out["year"] = subject_year

    for chapter in subject.get("chapters", []):
        chapter_name = chapter.get("chapter", "")

        if not chapter_started:
            if args.start_chapter and chapter_name == args.start_chapter:
                chapter_started = True
                topic_started = args.start_topic is None
            else:
                current_topic += len(chapter.get("topics", []))
                continue

        chap_out = find_chapter(subj_out["chapters"], chapter_name)
        if not chap_out:
            chap_out = {
                "chapter": chapter_name,
                "topics": []
            }
            subj_out["chapters"].append(chap_out)

        for t in chapter.get("topics", []):
            current_topic += 1
            topic_name = t.get("topic") if isinstance(t, dict) else None
            if not topic_name:
                continue

            if not topic_started:
                if args.start_topic and topic_name == args.start_topic:
                    topic_started = True
                else:
                    continue

            existing_topic = find_topic(chap_out["topics"], topic_name)
            if existing_topic and existing_topic.get("definition"):
                print(f"[SKIP] Already exists: {subject_name} > {chapter_name} > {topic_name}")
                continue

            print(f"[{current_topic}/{total_topics}] [GENERATING] {subject_name} > {chapter_name} > {topic_name}")
            try:
                definition = generate_definition(subject_name, chapter_name, topic_name)
            except Exception as e:
                print(f"[ERROR] {topic_name}: {e}")
                definition = ""
            definition = clean_response_text(definition, topic_name)

            if existing_topic:
                existing_topic["definition"] = definition
            else:
                chap_out["topics"].append({
                    "topic": topic_name,
                    "definition": definition
                })

            # Save immediately after each topic is generated for incremental updates
            save_output(output)

            time.sleep(DELAY)

save_output(output)
print(f"Definitions written to {OUTPUT_FILE}")
