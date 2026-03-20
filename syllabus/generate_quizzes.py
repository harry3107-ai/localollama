import argparse
import requests
import json
import time
import os

# Configuration
API_URL = "http://localhost:11434/api/generate"
MODEL = "gemma:2b"
DELAY = 1  # seconds between requests

def clean_json_response(text):
    """Attempts to strip out markdown to leave pure JSON, and parses it."""
    if not text:
        return []

    raw = text.strip()
    # Remove markdown code block markers if the model included them
    if raw.startswith("```json"):
        raw = raw[7:]
    elif raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    
    raw = raw.strip()
    
    try:
        data = json.loads(raw)
        return data
    except json.JSONDecodeError as e:
        print(f"[JSON ERROR] Failed to parse response: {e}")
        return []

def generate_quizzes(subject, chapter, topic, definition):
    prompt = f"""
You are an expert educational content creator. Based on the following definition of the topic '{topic}' in the chapter '{chapter}' for the subject '{subject}', generate exactly 5 quiz questions.
- 2 questions MUST have multiple correct answers (set type to "multiple_correct").
- 3 questions MUST have a single correct answer (set type to "single_correct").

Definition:
{definition}

Output the result STRICTLY as a JSON array of objects with the following structure, with no additional text or markdown formatting:
[
  {{
    "question": "Question text",
    "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
    "answer": "Correct Option", // For single_correct this is a string. For multiple_correct this is a list of strings: ["Correct Option 1", "Correct Option 2"]
    "type": "single_correct" // or "multiple_correct"
  }}
]
"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.3, # lower temperature for rigid JSON structure output
        "top_p": 0.9,
    }

    response = requests.post(API_URL, json=payload, timeout=300)
    response.raise_for_status()
    result = response.json()
    quiz_text = result.get("response", "")
    return clean_json_response(quiz_text)

def export_to_markdown(subjects, md_filename):
    """Renders the subjects and quizzes into a readable Markdown file."""
    with open(md_filename, "w", encoding="utf-8") as f:
        for subject in subjects:
            f.write(f"# {subject.get('subject', 'Unknown Subject')} (Year {subject.get('year', '')})\n\n")
            for chapter in subject.get("chapters", []):
                f.write(f"## {chapter.get('chapter', 'Unknown Chapter')}\n\n")
                for topic in chapter.get("topics", []):
                    f.write(f"### {topic.get('topic', 'Unknown Topic')}\n\n")
                    f.write(f"**Definition:**\n{topic.get('definition', '')}\n\n")
                    
                    quizzes = topic.get("quizzes", [])
                    if quizzes:
                        f.write("**Quizzes:**\n\n")
                        for i, quiz in enumerate(quizzes, 1):
                            f.write(f"**Q{i}: {quiz.get('question', '')}**\n\n")
                            answers = quiz.get("answer", [])
                            # Normalize single_correct string answers into a list for easy checking
                            if isinstance(answers, str):
                                answers = [answers]
                            for option in quiz.get("options", []):
                                mark = "x" if option in answers else " "
                                f.write(f"- [{mark}] {option}\n")
                            f.write("\n")
                    f.write("---\n\n")

def main():
    parser = argparse.ArgumentParser(description='Generate AI quizzes for topics.')
    parser.add_argument('--input', type=str, required=True, help='Input JSON file containing definitions')
    parser.add_argument('--output', type=str, default='sample-quiz.json', help='Output JSON file')
    parser.add_argument('--output-md', type=str, default='sample-quiz.md', help='Output Markdown file')
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        subjects = json.load(f)

    if not isinstance(subjects, list):
        subjects = [subjects]

    for subject in subjects:
        subject_name = subject.get("subject", "")
        for chapter in subject.get("chapters", []):
            chapter_name = chapter.get("chapter", "")
            for t in chapter.get("topics", []):
                topic_name = t.get("topic", "")
                definition = t.get("definition", "")
                
                # Skip if we already have quizzes generated
                if "quizzes" in t and t["quizzes"]:
                    continue
                
                print(f"[GENERATING QUIZZES] {subject_name} > {chapter_name} > {topic_name}")
                try:
                    quizzes = generate_quizzes(subject_name, chapter_name, topic_name, definition)
                    t["quizzes"] = quizzes
                except Exception as e:
                    print(f"[ERROR] {topic_name}: {e}")
                    t["quizzes"] = []
                
                # Save incrementally so we don't lose progress
                with open(args.output, "w", encoding="utf-8") as out_f:
                    json.dump(subjects, out_f, ensure_ascii=False, indent=2)
                
                time.sleep(DELAY)

    print(f"Quizzes written to {args.output}")
    
    export_to_markdown(subjects, args.output_md)
    print(f"Markdown rendered to {args.output_md}")

if __name__ == "__main__":
    main()