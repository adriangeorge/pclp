#!/usr/bin/env python3
"""
Question Bank Encryption Utility

This script encrypts all CSV question files in the questions directory
using AES encryption with a user-provided password.

Usage:
    python encrypt_questions.py
    python encrypt_questions.py --password "your_password"
    python encrypt_questions.py --questions-dir "../questions" --output-dir "encrypted"
"""

import os
import sys
import argparse
import getpass
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

def derive_key_from_password(password: str, salt: bytes) -> bytes:
    """Derive encryption key from password using PBKDF2."""
    password_bytes = password.encode('utf-8')
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,  # Recommended minimum
    )
    key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
    return key

def encrypt_file(file_path: Path, password: str, output_dir: Path, in_place: bool = False) -> bool:
    """Encrypt a single CSV file."""
    try:
        # Generate a random salt for this file
        salt = os.urandom(16)
        
        # Derive key from password and salt
        key = derive_key_from_password(password, salt)
        fernet = Fernet(key)
        
        # Read the original file
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        # Encrypt the data
        encrypted_data = fernet.encrypt(file_data)
        
        # Determine output file path
        if in_place:
            # Replace original file with encrypted version
            output_file = file_path.with_suffix('.encrypted')
        else:
            # Save to output directory
            output_file = output_dir / f"{file_path.stem}.encrypted"
        
        # Write salt + encrypted data to output file
        with open(output_file, 'wb') as f:
            f.write(salt)  # First 16 bytes are the salt
            f.write(encrypted_data)  # Rest is encrypted data
        
        # If in-place, remove the original file
        if in_place:
            file_path.unlink()
            print(f"[OK] Encrypted in-place: {file_path.name} -> {output_file.name}")
        else:
            print(f"[OK] Encrypted: {file_path.name} -> {output_file.name}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] Failed to encrypt {file_path.name}: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Encrypt question bank CSV files")
    parser.add_argument("--password", "-p", help="Encryption password (will prompt if not provided)")
    parser.add_argument("--questions-dir", "-q", default="../questions", 
                       help="Directory containing question CSV files (default: ../questions)")
    parser.add_argument("--output-dir", "-o", default="encrypted_questions",
                       help="Directory to save encrypted files (default: encrypted_questions)")
    parser.add_argument("--in-place", "-i", action="store_true",
                       help="Encrypt files in-place (replaces original files)")
    parser.add_argument("--include-mappings", action="store_true",
                       help="Also encrypt the mappings.yaml file")
    
    args = parser.parse_args()
    
    # Get password
    if args.password:
        password = args.password
    else:
        password = getpass.getpass("Enter encryption password: ")
        confirm_password = getpass.getpass("Confirm password: ")
        if password != confirm_password:
            print("[ERROR] Passwords do not match!")
            sys.exit(1)
    
    if not password:
        print("[ERROR] Password cannot be empty!")
        sys.exit(1)
    
    # Setup directories
    questions_dir = Path(args.questions_dir)
    
    if args.in_place:
        output_dir = questions_dir  # Use same directory for in-place
        print(f"[ENCRYPT] Encrypting question bank in-place in {questions_dir}")
    else:
        output_dir = Path(args.output_dir)
        # Create output directory for non-in-place encryption
        output_dir.mkdir(exist_ok=True)
        print(f"[ENCRYPT] Encrypting question bank from {questions_dir} to {output_dir}")
    
    if not questions_dir.exists():
        print(f"[ERROR] Questions directory not found: {questions_dir}")
        sys.exit(1)
    print("=" * 60)
    
    # Find all CSV files
    csv_files = list(questions_dir.glob("cat_*.csv"))
    
    if not csv_files:
        print(f"[ERROR] No CSV files found in {questions_dir}")
        sys.exit(1)
    
    # Encrypt each file
    encrypted_count = 0
    total_files = len(csv_files)
    
    for csv_file in csv_files:
        if encrypt_file(csv_file, password, output_dir, args.in_place):
            encrypted_count += 1
    
    # Optionally encrypt mappings.yaml
    if args.include_mappings:
        mappings_file = questions_dir / "mappings.yaml"
        if mappings_file.exists():
            if encrypt_file(mappings_file, password, output_dir, args.in_place):
                total_files += 1
                encrypted_count += 1
        else:
            print(f"[WARNING] mappings.yaml not found in {questions_dir}")
    
    print("=" * 60)
    print(f"[RESULT] Encryption completed: {encrypted_count}/{total_files} files encrypted")
    
    if encrypted_count == total_files:
        print("[SUCCESS] All files encrypted successfully!")
        if args.in_place:
            print(f"[INFO] Files encrypted in-place in: {questions_dir.absolute()}")
            print()
            print("[IMPORTANT]")
            print("   - Original files have been REPLACED with encrypted versions")
            print("   - Keep your password safe! Without it, the files cannot be decrypted")
            print("   - Use decrypt_questions.py --in-place to decrypt back to original format")
        else:
            print(f"[INFO] Encrypted files saved to: {output_dir.absolute()}")
            print()
            print("[IMPORTANT]")
            print("   - Keep your password safe! Without it, the files cannot be decrypted")
            print("   - Consider backing up the original files before deleting them")
            print("   - Use decrypt_questions.py to decrypt when needed")
    else:
        print("[WARNING] Some files failed to encrypt. Check the error messages above.")
        
if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[CANCELLED] Operation cancelled by user")
        sys.exit(1)
    except ImportError as e:
        if "cryptography" in str(e):
            print("[ERROR] Missing required library. Install with:")
            print("   pip install cryptography")
            sys.exit(1)
        else:
            raise