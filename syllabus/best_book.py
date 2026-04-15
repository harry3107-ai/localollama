import json
import os
import requests
import time

# Configuration
TEMPLATE_FILE = "bestbook-template.json"
OUTPUT_FILE = "best-books-updated.json"
API_URL = "http://localhost:11434/api/generate"
MODEL = "gemma:2b"
DELAY = 1  # seconds between requests
# Removed ADDITIONAL_TAG - will create subject-specific tags instead


def load_template(template_path):
    """Load the bestbook template JSON file."""
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template file not found: {template_path}")
    
    with open(template_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def generate_book_info(subject_name, sub_exam_name):
    """
    Use API to generate 2 book titles, authors, and descriptions for a subject.
    
    Replacements applied per book:
    1. Title - Generated from API
    2. Author - Generated from API
    3. Description - Generated from API
    """
    prompt = (
        f"Generate TWO different recommended books for the subject '{subject_name}' at '{sub_exam_name}' level. "
        f"Provide ONLY a JSON array with exactly two objects, each with these three fields (no markdown, no extra text): "
        f"[{{\"title\": \"book title 1\", \"author\": \"author name 1\", \"description\": \"one sentence description 1\"}}, "
        f"{{\"title\": \"book title 2\", \"author\": \"author name 2\", \"description\": \"one sentence description 2\"}}]. "
    )
    
    try:
        response = requests.post(
            API_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.7
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        # Extract and parse the response
        raw_response = result.get("response", "").strip()
        
        # Debug output
        if not raw_response:
            print(f"    ❌ Empty API response")
            return None
        
        # Try to extract JSON from response
        if "[" in raw_response and "]" in raw_response:
            json_start = raw_response.find("[")
            json_end = raw_response.rfind("]") + 1
            json_str = raw_response[json_start:json_end]
            
            books_list = json.loads(json_str)
            
            # Ensure we have at least 2 books
            if isinstance(books_list, list) and len(books_list) >= 2:
                return [
                    {
                        "title": books_list[0].get("title", "Recommended Book 1"),
                        "author": books_list[0].get("author", "Author Name"),
                        "description": books_list[0].get("description", "Best reference material.")
                    },
                    {
                        "title": books_list[1].get("title", "Recommended Book 2"),
                        "author": books_list[1].get("author", "Author Name"),
                        "description": books_list[1].get("description", "Alternative reference material.")
                    }
                ]
            else:
                print(f"    ❌ Could not parse 2 books from response")
                return None
        else:
            print(f"    ❌ No JSON array found in response")
            return None
    
    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON Parse Error: {str(e)}")
        return None
    except Exception as e:
        print(f"  ⚠ API Error: {str(e)}")
        return None


def generate_contextual_tags(subject_name):
    """
    Generate 1-2 contextual tags based on the subject name.
    These tags will be in addition to exam, class, and subject tags.
    """
    prompt = (
        f"For the subject '{subject_name}', suggest 1-2 specific category or skill tags "
        f"(e.g., 'Problem Solving', 'Practical Skills', 'Theory', 'Application', 'Memorization', etc.). "
        f"Provide ONLY a JSON object with format: {{\"tags\": [\"tag1\", \"tag2\"]}} (max 2 tags, no extra text)."
    )
    
    try:
        response = requests.post(
            API_URL,
            json={
                "model": MODEL,
                "prompt": prompt,
                "stream": False,
                "temperature": 0.6
            },
            timeout=30
        )
        response.raise_for_status()
        result = response.json()
        
        raw_response = result.get("response", "").strip()
        
        if not raw_response:
            print(f"    ❌ Empty tag API response")
            return []
        
        if "{" in raw_response and "}" in raw_response:
            json_start = raw_response.find("{")
            json_end = raw_response.rfind("}") + 1
            json_str = raw_response[json_start:json_end]
            tag_obj = json.loads(json_str)
            
            if "tags" in tag_obj and isinstance(tag_obj["tags"], list) and len(tag_obj["tags"]) > 0:
                return tag_obj["tags"][:2]  # Return max 2 tags
            else:
                print(f"    ❌ No valid tags in response")
                return []
        else:
            print(f"    ❌ No JSON object found in tag response")
            return []
    
    except json.JSONDecodeError as e:
        print(f"  ⚠ Tag JSON Parse Error: {str(e)}")
        return []
    except Exception as e:
        print(f"  ⚠ Tag Generation Error: {str(e)}")
        return []


def save_updated_books(books_data, output_path):
    """Save updated books data to output JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(books_data, f, indent=2, ensure_ascii=False)


def fix_existing_tags(books_data, output_path):
    """
    Fix the tags for already processed subjects (done=true).
    Replace the old NCERT tag with proper contextual tags.
    """
    total_subjects = len(books_data)
    fixed_count = 0
    
    print("\n" + "="*60)
    print("FIXING EXISTING SUBJECTS (removing NCERT, adding contextual tags)")
    print("="*60 + "\n")
    
    for idx, entry in enumerate(books_data, 1):
        is_done = entry.get("done", False)
        
        # Only fix subjects that are already done
        if not is_done:
            continue
        
        subject_name = entry.get("subjectName", {}).get("en", "Unknown")
        sub_exam_name = entry.get("subExamName", {}).get("en", "Unknown")
        exam_name = entry.get("examName", {}).get("en", "Unknown")
        
        print(f"[{fixed_count + 1}] Fixing: {subject_name}")
        
        # Generate new contextual tags
        print(f"  → Generating contextual tags...")
        contextual_tags = generate_contextual_tags(subject_name)
        
        # Create new tag structure without NCERT
        base_tags = [exam_name, sub_exam_name, subject_name]
        all_tags = base_tags + contextual_tags
        
        # Update tags for all books
        if "books" in entry:
            for book_idx, book in enumerate(entry["books"], 1):
                # Update with new tags
                book["tags"] = all_tags.copy()
                
                tag_display = ", ".join(book["tags"])
                print(f"  ✓ Book {book_idx} Tags updated ({len(book['tags'])}): {tag_display}")
        
        fixed_count += 1
        
        # Save after each subject
        save_updated_books(books_data, output_path)
        
        # Delay between API calls
        time.sleep(DELAY)
    
    print(f"\n{'='*60}")
    print(f"✓ Total Fixed: {fixed_count}")
    print(f"{'='*60}\n")
    
    return books_data


def update_books_with_api(books_data, output_path):
    """
    Update all subjects in books data using API.
    Saves file after each subject is processed.
    Skips subjects already marked as done: true
    
    For each subject (2 books):
    - Replacement 1: Title (from API)
    - Replacement 2: Author (from API)
    - Replacement 3: Description (from API)
    - Append: Add 3+ contextual tags (Exam, Class, Subject + 1-2 contextual)
    - Mark: Set "done": true
    """
    updated_data = books_data
    total_subjects = len(updated_data)
    replacements_count = 0
    append_count = 0
    skipped_count = 0
    failed_count = 0
    
    for idx, entry in enumerate(updated_data, 1):
        subject_name = entry.get("subjectName", {}).get("en", "Unknown")
        sub_exam_name = entry.get("subExamName", {}).get("en", "Unknown")
        exam_name = entry.get("examName", {}).get("en", "Unknown")
        is_done = entry.get("done", False)
        
        # Skip if already processed
        if is_done:
            print(f"[{idx}/{total_subjects}] ⏭️  SKIPPED (already done): {subject_name}")
            skipped_count += 1
            continue
        
        print(f"\n[{idx}/{total_subjects}] Processing: {subject_name}")
        
        # Generate book info from API (2 books)
        print(f"  → Calling API for 2 book recommendations...")
        books_info = generate_book_info(subject_name, sub_exam_name)
        
        # Generate contextual tags
        print(f"  → Generating contextual tags...")
        contextual_tags = generate_contextual_tags(subject_name)
        
        if books_info:
            # Create base tags with exam, class, subject + contextual tags
            base_tags = [exam_name, sub_exam_name, subject_name]
            all_tags = base_tags + contextual_tags
            
            # Clear existing books and add 2 new ones
            entry["books"] = []
            
            for book_idx, book_info in enumerate(books_info, 1):
                book = {
                    "title": book_info["title"],
                    "author": book_info["author"],
                    "description": book_info["description"],
                    "tags": all_tags.copy()
                }
                entry["books"].append(book)
                print(f"  ✓ [REPLACEMENT {(book_idx-1)*3 + 1}] Book {book_idx} Title: {book_info['title'][:50]}...")
                print(f"  ✓ [REPLACEMENT {(book_idx-1)*3 + 2}] Book {book_idx} Author: {book_info['author']}")
                print(f"  ✓ [REPLACEMENT {(book_idx-1)*3 + 3}] Book {book_idx} Description updated")
                replacements_count += 3
            
            # Show tags for both books
            for book_idx, book in enumerate(entry["books"], 1):
                if "tags" in book and isinstance(book["tags"], list):
                    tag_display = ", ".join(book["tags"])
                    print(f"  ✓ [APPEND] Book {book_idx} Tags ({len(book['tags'])}): {tag_display}")
                    append_count += 1
        else:
            print(f"  ❌ FAILED: Could not generate book information from API")
            failed_count += 1
        
        # Mark as done
        entry["done"] = True
        print(f"  ✓ [DONE] Marked as completed")
        
        # Save file after each subject is processed
        print(f"  💾 Saving file...")
        save_updated_books(updated_data, output_path)
        
        # Add delay between API calls
        if idx < total_subjects:
            time.sleep(DELAY)
    
    print(f"\n{'='*60}")
    print(f"✓ Total Subjects: {total_subjects}")
    print(f"✓ Skipped (already done): {skipped_count}")
    print(f"✓ Newly Processed: {total_subjects - skipped_count}")
    print(f"✓ Successfully Generated: {total_subjects - skipped_count - failed_count}")
    print(f"✓ Failed: {failed_count}")
    print(f"✓ Total Replacements Applied: {replacements_count}")
    print(f"✓ Total Appends Applied: {append_count}")
    print(f"{'='*60}\n")
    
    return updated_data


def save_updated_books(books_data, output_path):
    """Save updated books data to output JSON file."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(books_data, f, indent=2, ensure_ascii=False)
    print(f"✓ Updated books saved to: {output_path}")


def main():
    """Main execution function."""
    try:
        print("=" * 60)
        print("BEST BOOKS TEMPLATE PROCESSOR - API EDITION")
        print("=" * 60)
        print(f"API URL: {API_URL}")
        print(f"Model: {MODEL}")
        print(f"Output: {OUTPUT_FILE}")
        print("=" * 60)
        
        # Check if output file exists
        has_existing = os.path.exists(OUTPUT_FILE) and os.path.getsize(OUTPUT_FILE) > 100
        
        if has_existing:
            print("\n[MENU] Choose an option:")
            print("1. Process new subjects (skip done=true)")
            print("2. Fix existing subjects (re-generate tags for all done=true)")
            choice = input("Enter 1 or 2: ").strip()
        else:
            choice = "1"
            print("\n[INFO] No existing output file found. Starting fresh.\n")
        
        # Step 1: Load template or output file
        print("[STEP 1] Loading data...")
        if choice == "2" and has_existing:
            print(f"✓ Loading existing file: {OUTPUT_FILE}")
            books_data = load_template(OUTPUT_FILE)
        elif has_existing:
            print(f"✓ Found existing output file: {OUTPUT_FILE} (resuming from checkpoint)")
            books_data = load_template(OUTPUT_FILE)
        else:
            print(f"✓ Loading template: {TEMPLATE_FILE}")
            books_data = load_template(TEMPLATE_FILE)
        
        print(f"✓ Loaded {len(books_data)} subject entries\n")
        
        # Step 2: Process or fix subjects
        if choice == "2" and has_existing:
            print("[STEP 2] Fixing existing subjects (removing NCERT, adding contextual tags)...")
            updated_data = fix_existing_tags(books_data, OUTPUT_FILE)
        else:
            print("[STEP 2] Processing new subjects...")
            print("✓ Subjects marked as 'done': true will be skipped")
            print("✓ File will be saved after each subject is processed\n")
            updated_data = update_books_with_api(books_data, OUTPUT_FILE)
        
        print("\n" + "=" * 60)
        print("PROCESS COMPLETED SUCCESSFULLY!")
        print(f"Final output saved to: {OUTPUT_FILE}")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
