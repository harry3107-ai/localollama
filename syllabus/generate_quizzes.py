import argparse
import requests
import json
import time
import os
import glob

# Configuration
API_URL = "http://localhost:11434/api/generate"
MODEL = "mistral"  # Changed from "gemma:2b" to "mistral" (7B) for better JSON/quiz generation
DELAY = 1  # seconds between requests
MAX_RETRIES = 3  # retry failed quizzes
RETRY_DELAY = 2  # seconds between retries


def parse_llm_json(text):
    """Parses the LLM output into JSON. It only removes the outer ```json markers to prevent parse errors, keeping all inner markdown intact."""
    if not text:
        return None

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
        return data if isinstance(data, list) else None
    except json.JSONDecodeError as e:
        print(f"    ❌ JSON Parse Error: {e}")
        return None


def validate_quizzes(quizzes):
    """
    Validate that quizzes meet requirements:
    - Exactly 5 questions total
    - Exactly 2 multiple_correct type
    - Exactly 3 single_correct type
    - All answers exist in the options list
    """
    if not quizzes or not isinstance(quizzes, list):
        return False, "Not a valid list"
    
    if len(quizzes) != 5:
        return False, f"Expected 5 questions, got {len(quizzes)}"
    
    multiple_count = 0
    single_count = 0
    
    for idx, quiz in enumerate(quizzes):
        # Check required fields
        if not all(key in quiz for key in ["question", "options", "answer", "type"]):
            return False, f"Question {idx+1}: Missing required fields"
        
        question_type = quiz.get("type", "").lower()
        options = quiz.get("options", [])
        answer = quiz.get("answer")
        
        # Validate options
        if not options or len(options) < 2:
            return False, f"Question {idx+1}: Need at least 2 options, got {len(options)}"
        
        # Count question types
        if question_type == "multiple_correct":
            multiple_count += 1
            # Validate answer is a list
            if not isinstance(answer, list):
                return False, f"Question {idx+1}: multiple_correct answer must be a list"
            # Validate all answers exist in options
            for ans in answer:
                if ans not in options:
                    return False, f"Question {idx+1}: Answer '{ans}' not in options"
        elif question_type == "single_correct":
            single_count += 1
            # Validate answer is a string
            if not isinstance(answer, str):
                return False, f"Question {idx+1}: single_correct answer must be a string"
            # Validate answer exists in options
            if answer not in options:
                return False, f"Question {idx+1}: Answer '{answer}' not in options"
        else:
            return False, f"Question {idx+1}: Invalid type '{question_type}'"
    
    if multiple_count != 2:
        return False, f"Expected 2 multiple_correct, got {multiple_count}"
    
    if single_count != 3:
        return False, f"Expected 3 single_correct, got {single_count}"
    
    return True, "Valid"


def generate_multiple_choice_questions(subject, chapter, topic, definition, attempt=1):
    """Generate ONLY 2 multiple choice questions with multiple correct answers."""
    prompt = f"""You are an expert educational content creator. Based on the definition of '{topic}' in '{chapter}' ({subject}), generate EXACTLY 2 quiz questions where each question has MULTIPLE correct answers.

CRITICAL RULES:
1. Generate EXACTLY 2 questions
2. Each question MUST have type: "multiple_correct"
3. Each question MUST have 4 options
4. For each question, the "answer" MUST be a JSON array of 2-3 correct options from the options list
5. All answer values MUST exactly match options in the options array

Definition:
{definition}

Output ONLY valid JSON array. No extra text:
[
  {{
    "question": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": ["Option A", "Option C"],
    "type": "multiple_correct"
  }},
  {{
    "question": "Another question?",
    "options": ["Option X", "Option Y", "Option Z", "Option W"],
    "answer": ["Option X", "Option Y"],
    "type": "multiple_correct"
  }}
]"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.7,
        "top_p": 0.7,
        "num_predict": 300
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=20)
        response.raise_for_status()
        result = response.json()
        quiz_text = result.get("response", "")
        
        quizzes = parse_llm_json(quiz_text)
        
        # Validate: should have exactly 2 questions, all multiple_correct type
        if not quizzes or not isinstance(quizzes, list):
            if attempt < MAX_RETRIES:
                print(f"    ⚠️  Invalid response format. Retry {attempt}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
                return generate_multiple_choice_questions(subject, chapter, topic, definition, attempt + 1)
            return None
        
        if len(quizzes) != 2:
            print(f"    ⚠️  Expected 2 questions, got {len(quizzes)}")
            if attempt < MAX_RETRIES:
                print(f"    🔄 Retry {attempt}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
                return generate_multiple_choice_questions(subject, chapter, topic, definition, attempt + 1)
            return None
        
        # Validate each question
        valid = True
        for idx, quiz in enumerate(quizzes):
            if quiz.get("type") != "multiple_correct":
                print(f"    ⚠️  Question {idx+1}: Wrong type (expected multiple_correct)")
                valid = False
                break
            
            answer = quiz.get("answer")
            options = quiz.get("options", [])
            
            if not isinstance(answer, list):
                print(f"    ⚠️  Question {idx+1}: Answer must be a list")
                valid = False
                break
            
            for ans in answer:
                if ans not in options:
                    print(f"    ⚠️  Question {idx+1}: Answer '{ans}' not in options")
                    valid = False
                    break
        
        if not valid and attempt < MAX_RETRIES:
            print(f"    🔄 Retry {attempt}/{MAX_RETRIES}...")
            time.sleep(RETRY_DELAY)
            return generate_multiple_choice_questions(subject, chapter, topic, definition, attempt + 1)
        
        return quizzes if valid else None
    
    except requests.RequestException as e:
        print(f"    ⚠️  API Error: {e}")
        if attempt < MAX_RETRIES:
            print(f"    🔄 Retry {attempt}/{MAX_RETRIES}...")
            time.sleep(RETRY_DELAY)
            return generate_multiple_choice_questions(subject, chapter, topic, definition, attempt + 1)
        return None
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return None


def generate_single_choice_questions(subject, chapter, topic, definition, attempt=1):
    """Generate ONLY 3 single choice questions with one correct answer each."""
    prompt = f"""You are an expert educational content creator. Based on the definition of '{topic}' in '{chapter}' ({subject}), generate EXACTLY 3 quiz questions where each question has ONE correct answer.

CRITICAL RULES:
1. Generate EXACTLY 3 questions
2. Each question MUST have type: "single_correct"
3. Each question MUST have 4 options
4. For each question, the "answer" MUST be a string that is one of the options
5. Answer value MUST exactly match one option from the options array

Definition:
{definition}

Output ONLY valid JSON array. No extra text:
[
  {{
    "question": "Question text here?",
    "options": ["Option A", "Option B", "Option C", "Option D"],
    "answer": "Option A",
    "type": "single_correct"
  }},
  {{
    "question": "Another question?",
    "options": ["Option X", "Option Y", "Option Z", "Option W"],
    "answer": "Option X",
    "type": "single_correct"
  }},
  {{
    "question": "Third question?",
    "options": ["Choice 1", "Choice 2", "Choice 3", "Choice 4"],
    "answer": "Choice 2",
    "type": "single_correct"
  }}
]"""

    payload = {
        "model": MODEL,
        "prompt": prompt,
        "stream": False,
        "temperature": 0.7,
        "top_p": 0.7,
        "num_predict": 300
    }

    try:
        response = requests.post(API_URL, json=payload, timeout=20)
        response.raise_for_status()
        result = response.json()
        quiz_text = result.get("response", "")
        
        quizzes = parse_llm_json(quiz_text)
        
        # Validate: should have exactly 3 questions, all single_correct type
        if not quizzes or not isinstance(quizzes, list):
            if attempt < MAX_RETRIES:
                print(f"    ⚠️  Invalid response format. Retry {attempt}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
                return generate_single_choice_questions(subject, chapter, topic, definition, attempt + 1)
            return None
        
        if len(quizzes) != 3:
            print(f"    ⚠️  Expected 3 questions, got {len(quizzes)}")
            if attempt < MAX_RETRIES:
                print(f"    🔄 Retry {attempt}/{MAX_RETRIES}...")
                time.sleep(RETRY_DELAY)
                return generate_single_choice_questions(subject, chapter, topic, definition, attempt + 1)
            return None
        
        # Validate each question
        valid = True
        for idx, quiz in enumerate(quizzes):
            if quiz.get("type") != "single_correct":
                print(f"    ⚠️  Question {idx+1}: Wrong type (expected single_correct)")
                valid = False
                break
            
            answer = quiz.get("answer")
            options = quiz.get("options", [])
            
            if not isinstance(answer, str):
                print(f"    ⚠️  Question {idx+1}: Answer must be a string")
                valid = False
                break
            
            if answer not in options:
                print(f"    ⚠️  Question {idx+1}: Answer '{answer}' not in options")
                valid = False
                break
        
        if not valid and attempt < MAX_RETRIES:
            print(f"    🔄 Retry {attempt}/{MAX_RETRIES}...")
            time.sleep(RETRY_DELAY)
            return generate_single_choice_questions(subject, chapter, topic, definition, attempt + 1)
        
        return quizzes if valid else None
    
    except requests.RequestException as e:
        print(f"    ⚠️  API Error: {e}")
        if attempt < MAX_RETRIES:
            print(f"    🔄 Retry {attempt}/{MAX_RETRIES}...")
            time.sleep(RETRY_DELAY)
            return generate_single_choice_questions(subject, chapter, topic, definition, attempt + 1)
        return None
    except Exception as e:
        print(f"    ❌ Error: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Generate AI quizzes for topics.')
    parser.add_argument('--input-pattern', type=str, default='data/output/official_syllabus_*-topic.json', help='Input JSON files pattern')
    args = parser.parse_args()

    file_list = glob.glob(args.input_pattern)
    if not file_list:
        print(f"No files found matching '{args.input_pattern}'")
        return

    total_processed = 0
    total_success = 0
    total_failed = 0
    total_skipped = 0

    for filepath in file_list:
        print(f"\n{'='*60}")
        print(f"Processing File: {filepath}")
        print(f"{'='*60}")
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                subjects = json.load(f)
        except Exception as e:
            print(f"❌ Failed to load file: {e}")
            continue

        if not isinstance(subjects, list):
            subjects = [subjects]

        for subject in subjects:
            subject_name = subject.get("subject", "")
            for chapter in subject.get("chapters", []):
                chapter_name = chapter.get("chapter", "")
                for t in chapter.get("topics", []):
                    topic_name = t.get("topic", "")
                    definition = t.get("definition", "")
                    
                    # Skip if we already have valid quizzes
                    if "quizzes" in t and t["quizzes"] and isinstance(t["quizzes"], list) and len(t["quizzes"]) == 5:
                        is_valid, _ = validate_quizzes(t["quizzes"])
                        if is_valid:
                            print(f"  ⏭️  SKIP: Valid quizzes exist")
                            total_skipped += 1
                            continue
                    
                    total_processed += 1
                    print(f"\n[{total_processed}] {subject_name} > {chapter_name} > {topic_name}")
                    
                    try:
                        # Generate 2 multiple choice questions
                        print(f"  → Generating 2 multiple choice questions...")
                        multiple_quizzes = generate_multiple_choice_questions(subject_name, chapter_name, topic_name, definition)
                        
                        if not multiple_quizzes:
                            print(f"  ❌ Failed to generate multiple choice questions")
                            t["quizzes"] = []
                            total_failed += 1
                        else:
                            print(f"  ✓ Generated 2 multiple choice questions")
                            
                            # Generate 3 single choice questions
                            print(f"  → Generating 3 single choice questions...")
                            single_quizzes = generate_single_choice_questions(subject_name, chapter_name, topic_name, definition)
                            
                            if not single_quizzes:
                                print(f"  ❌ Failed to generate single choice questions")
                                t["quizzes"] = []
                                total_failed += 1
                            else:
                                print(f"  ✓ Generated 3 single choice questions")
                                
                                # Combine both types
                                combined_quizzes = multiple_quizzes + single_quizzes
                                is_valid, validation_msg = validate_quizzes(combined_quizzes)
                                
                                if is_valid:
                                    t["quizzes"] = combined_quizzes
                                    total_success += 1
                                    print(f"  ✓✓ SUCCESS: All 5 quizzes generated and validated")
                                else:
                                    print(f"  ❌ Final validation failed: {validation_msg}")
                                    t["quizzes"] = []
                                    total_failed += 1
                    except Exception as e:
                        print(f"  ❌ ERROR: {e}")
                        t["quizzes"] = []
                        total_failed += 1
                    
                    # Save incrementally back to the SAME file after successful generation
                    try:
                        with open(filepath, "w", encoding="utf-8") as out_f:
                            json.dump(subjects, out_f, ensure_ascii=False, indent=2)
                        if t.get("quizzes"):
                            print(f"  💾 Saved to file")
                    except Exception as e:
                        print(f"  ⚠️  Failed to save: {e}")
                    
                    time.sleep(DELAY)

        print(f"\n{'='*60}")
        print(f"File Summary: {filepath}")
        print(f"{'='*60}")

    print(f"\n{'='*60}")
    print(f"OVERALL SUMMARY")
    print(f"{'='*60}")
    print(f"✓ Successfully generated: {total_success}")
    print(f"❌ Failed: {total_failed}")
    print(f"⏭️  Skipped (already valid): {total_skipped}")
    print(f"Total processed: {total_processed}")
    if total_processed > 0:
        success_rate = (total_success / total_processed) * 100
        print(f"Success rate: {success_rate:.1f}%")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()