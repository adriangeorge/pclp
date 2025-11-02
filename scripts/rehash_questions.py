#!/usr/bin/env python3
"""
Question Rehashing Script
Generates new hashes for all questions based on their question text content.
"""

import csv
import hashlib
import re
from pathlib import Path

def generate_hash(question_text: str) -> str:
    """Generate a consistent 8-character hash from question text."""
    # Clean the question text for consistent hashing
    cleaned_text = re.sub(r'[^\w\s]', '', question_text.lower().strip())
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text)
    
    # Generate MD5 hash and take first 8 characters
    hash_object = hashlib.md5(cleaned_text.encode('utf-8'))
    return hash_object.hexdigest()[:8]

def rehash_csv_file(file_path: Path) -> int:
    """Rehash all questions in a CSV file. Returns number of questions processed."""
    if not file_path.exists():
        print(f"File not found: {file_path}")
        return 0
    
    # Read all rows
    rows = []
    header = None
    with open(file_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        header = reader.fieldnames
        rows = list(reader)
    
    if not rows or not header:
        print(f"No data rows in {file_path}")
        return 0
    
    # Update hashes
    updated_count = 0
    for row in rows:
        if 'question' in row and 'hash' in row:
            old_hash = row['hash']
            new_hash = generate_hash(row['question'])
            
            if old_hash != new_hash:
                row['hash'] = new_hash
                updated_count += 1
                print(f"  Updated: {old_hash} -> {new_hash} | {row['question'][:50]}...")
    
    # Write back to file
    with open(file_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(rows)
    
    return len(rows)

def main():
    """Main function to rehash all question files."""
    questions_dir = Path("../questions")
    if not questions_dir.exists():
        questions_dir = Path("questions")
    
    if not questions_dir.exists():
        print("❌ Questions directory not found!")
        return
    
    print("🔄 Starting question rehashing process...")
    print(f"📁 Questions directory: {questions_dir.absolute()}")
    print()
    
    # Find all question CSV files
    csv_files = list(questions_dir.glob("cat_*.csv"))
    
    if not csv_files:
        print("❌ No question CSV files found!")
        return
    
    total_questions = 0
    total_files = 0
    
    for csv_file in sorted(csv_files):
        print(f"📝 Processing: {csv_file.name}")
        question_count = rehash_csv_file(csv_file)
        total_questions += question_count
        total_files += 1
        print(f"   ✅ Processed {question_count} questions")
        print()
    
    print("=" * 60)
    print(f"✅ Rehashing completed!")
    print(f"📊 Summary:")
    print(f"   • Files processed: {total_files}")
    print(f"   • Total questions: {total_questions}")
    print()
    print("🎯 All question hashes have been updated based on question text content.")

if __name__ == "__main__":
    main()