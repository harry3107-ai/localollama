import requests
import json
import time
import os
import re

# Configuration
API_URL = "http://localhost:11434/api/generate"
MODEL = "gemma:2b"
OUTPUT_FILE = "ai_responses.json"
DELAY = 2  # seconds between requests

# Load subjects JSON
with open("subjects.json", "r") as f:
    subjects_data = json.load(f)

# Load existing responses if file exists
if os.path.exists(OUTPUT_FILE):
    try:
        with open(OUTPUT_FILE, "r") as f:
            data_store = json.load(f)
    except json.JSONDecodeError:
        data_store = []
else:
    data_store = []

def extract_code(text):
    """Extract Python code from text returned by Ollama."""
    code_blocks = re.findall(r"```(?:python)?\n(.*?)```", text, re.DOTALL)
    return "\n".join(code_blocks).strip() if code_blocks else text.strip()

def already_generated(subject_name, chapter_name, topic_name):
    """Check if this topic was already generated."""
    for entry in data_store:
        if (entry["subject"] == subject_name and
            entry["chapter"] == chapter_name and
            entry["topic"] == topic_name):
            return True
    return False

def generate_topic_content(subject_name, chapter_name, topic_name):
    """Generate detailed content for a single topic."""
    prompt = f"Generate detailed educational content for the topic: '{topic_name}' in chapter '{chapter_name}' of subject '{subject_name}'. Include explanations, examples, and code if applicable."
    
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False
    }
    
    try:
        response = requests.post(API_URL, json=payload, timeout=300)
        response.raise_for_status()
        result = response.json()

        full_text = result.get("response", "")
        code_only = extract_code(full_text)

        entry = {
            "subject": subject_name,
            "chapter": chapter_name,
            "topic": topic_name,
            "response": code_only
        }

        data_store.append(entry)

        # Save after each generation for resumability
        temp_file = OUTPUT_FILE + ".tmp"
        with open(temp_file, "w") as f:
            json.dump(data_store, f, indent=2)
        os.replace(temp_file, OUTPUT_FILE)

        print(f"[OK] Generated topic: {subject_name} > {chapter_name} > {topic_name}")

    except Exception as e:
        print(f"[ERROR] Failed to generate topic: {topic_name}")
        print(e)

def process_chapters(subject_name, chapters):
    """Recursive loop over chapters and topics."""
    for chapter in chapters:
        chapter_name = chapter.get("name", "Unnamed Chapter")
        topics = chapter.get("topics", [])
        for topic in topics:
            if not already_generated(subject_name, chapter_name, topic):
                generate_topic_content(subject_name, chapter_name, topic)
                time.sleep(DELAY)

def process_subjects(subjects):
    """Recursive loop over subjects."""
    for subject in subjects:
        subject_name = subject.get("name", "Unnamed Subject")
        chapters = subject.get("chapters", [])
        process_chapters(subject_name, chapters)

# Start or resume generation
process_subjects(subjects_data["subjects"])

print("All content generation completed.")