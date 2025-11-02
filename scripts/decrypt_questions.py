#!/usr/bin/env python3
"""
Question Bank Decryption Utility

This script decrypts encrypted CSV question files back to their original format
using the same password that was used for encryption.

Usage:
    python decrypt_questions.py
    python decrypt_questions.py --password "your_password"
    python decrypt_questions.py --encrypted-dir "encrypted_questions" --output-dir "../questions"
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
        iterations=100000,  # Must match encryption iterations
    )
    key = base64.urlsafe_b64encode(kdf.derive(password_bytes))
    return key

def decrypt_file(encrypted_file_path: Path, password: str, output_dir: Path, in_place: bool = False) -> bool:
    """Decrypt a single encrypted file."""
    try:
        # Read the encrypted file
        with open(encrypted_file_path, 'rb') as f:
            file_data = f.read()
        
        if len(file_data) < 16:
            print(f"[ERROR] Invalid encrypted file: {encrypted_file_path.name} (too small)")
            return False
        
        # Extract salt (first 16 bytes) and encrypted data
        salt = file_data[:16]
        encrypted_data = file_data[16:]
        
        # Derive key from password and salt
        key = derive_key_from_password(password, salt)
        fernet = Fernet(key)
        
        # Decrypt the data
        decrypted_data = fernet.decrypt(encrypted_data)
        
        # Determine output filename and path
        if in_place:
            # Replace encrypted file with decrypted version in same location
            if encrypted_file_path.name.endswith('.encrypted'):
                # Remove .encrypted extension and restore original extension
                base_name = encrypted_file_path.stem
                if base_name.startswith('cat_') and not base_name.endswith('.csv'):
                    output_filename = f"{base_name}.csv"
                elif base_name == 'mappings':
                    output_filename = "mappings.yaml"
                else:
                    output_filename = base_name
                output_file = encrypted_file_path.parent / output_filename
            else:
                output_file = encrypted_file_path.with_suffix('.decrypted')
        else:
            # Save to output directory
            if encrypted_file_path.name.endswith('.encrypted'):
                # Remove .encrypted extension and restore original extension
                base_name = encrypted_file_path.stem
                if base_name.startswith('cat_') and not base_name.endswith('.csv'):
                    output_filename = f"{base_name}.csv"
                elif base_name == 'mappings':
                    output_filename = "mappings.yaml"
                else:
                    output_filename = base_name
            else:
                output_filename = f"{encrypted_file_path.stem}_decrypted"
            output_file = output_dir / output_filename
        
        # Write decrypted data to output file
        with open(output_file, 'wb') as f:
            f.write(decrypted_data)
        
        # If in-place, remove the encrypted file
        if in_place:
            encrypted_file_path.unlink()
            print(f"[OK] Decrypted in-place: {encrypted_file_path.name} -> {output_file.name}")
        else:
            print(f"[OK] Decrypted: {encrypted_file_path.name} -> {output_file.name}")
        
        return True
        
    except Exception as e:
        if "InvalidToken" in str(e) or "decrypt" in str(e).lower():
            print(f"[ERROR] Failed to decrypt {encrypted_file_path.name}: Incorrect password or corrupted file")
        else:
            print(f"[ERROR] Failed to decrypt {encrypted_file_path.name}: {e}")
        return False

def verify_decryption(output_dir: Path) -> bool:
    """Verify that decrypted files are valid CSV/YAML files."""
    try:
        csv_files = list(output_dir.glob("cat_*.csv"))
        if not csv_files:
            print("[WARNING] No CSV files found after decryption")
            return False
        
        # Try to read one CSV file to verify format
        test_file = csv_files[0]
        with open(test_file, 'r', encoding='utf-8') as f:
            first_line = f.readline().strip()
            if not first_line or 'category' not in first_line:
                print(f"[WARNING] Decrypted file may be corrupted: {test_file.name}")
                return False
        
        return True
    except Exception as e:
        print(f"[WARNING] Error verifying decrypted files: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Decrypt encrypted question bank files")
    parser.add_argument("--password", "-p", help="Decryption password (will prompt if not provided)")
    parser.add_argument("--encrypted-dir", "-e", default="../questions",
                       help="Directory containing encrypted files (default: questions)")
    parser.add_argument("--output-dir", "-o", default="../questions",
                       help="Directory to save decrypted files (default: ../questions)")
    parser.add_argument("--in-place", "-i", action="store_true",
                       help="Decrypt files in-place (replaces encrypted files with originals)")
    parser.add_argument("--overwrite", action="store_true",
                       help="Overwrite existing files in output directory")
    parser.add_argument("--verify", action="store_true", default=True,
                       help="Verify decrypted files are valid (default: true)")
    
    args = parser.parse_args()
    
    # Get password
    if args.password:
        password = args.password
    else:
        password = getpass.getpass("Enter decryption password: ")
    
    if not password:
        print("[ERROR] Password cannot be empty!")
        sys.exit(1)
    
    # Setup directories
    encrypted_dir = Path(args.encrypted_dir)
    
    if args.in_place:
        output_dir = encrypted_dir  # Use same directory for in-place
        print(f"[DECRYPT] Decrypting files in-place in {encrypted_dir}")
    else:
        output_dir = Path(args.output_dir)
        # Create output directory for non-in-place decryption
        output_dir.mkdir(exist_ok=True)
        print(f"[DECRYPT] Decrypting question bank from {encrypted_dir} to {output_dir}")
    
    if not encrypted_dir.exists():
        print(f"[ERROR] Encrypted directory not found: {encrypted_dir}")
        sys.exit(1)
    
    # Check if output directory has files and warn about overwriting
    if not args.in_place:
        existing_files = list(output_dir.glob("*"))
        if existing_files and not args.overwrite:
            print(f"[WARNING] Output directory {output_dir} contains {len(existing_files)} files")
            response = input("Continue and potentially overwrite files? (y/N): ")
            if response.lower() not in ['y', 'yes']:
                print("[CANCELLED] Operation cancelled")
                sys.exit(1)
    
    print("=" * 60)
    
    # Find all encrypted files
    encrypted_files = list(encrypted_dir.glob("*.encrypted"))
    
    if not encrypted_files:
        print(f"[ERROR] No encrypted files found in {encrypted_dir}")
        print("   Looking for files with .encrypted extension")
        sys.exit(1)
    
    # Decrypt each file
    decrypted_count = 0
    total_files = len(encrypted_files)
    
    for encrypted_file in encrypted_files:
        if decrypt_file(encrypted_file, password, output_dir, args.in_place):
            decrypted_count += 1
    
    print("=" * 60)
    print(f"[RESULT] Decryption completed: {decrypted_count}/{total_files} files decrypted")
    
    if decrypted_count == total_files:
        print("[SUCCESS] All files decrypted successfully!")
        
        # Verify decrypted files if requested and not in-place
        if args.verify and not args.in_place:
            print("[INFO] Verifying decrypted files...")
            if verify_decryption(output_dir):
                print("[SUCCESS] Decrypted files appear to be valid")
            else:
                print("[WARNING] Some decrypted files may be corrupted")
        
        if args.in_place:
            print(f"[INFO] Files decrypted in-place in: {encrypted_dir.absolute()}")
            print()
            print("[INFO] Next steps:")
            print("   - Encrypted files have been REPLACED with original files")
            print("   - Verify the decrypted files are correct")
            print("   - Your question bank is now ready to use")
        else:
            print(f"[INFO] Decrypted files saved to: {output_dir.absolute()}")
            print()
            print("[INFO] Next steps:")
            print("   - Verify the decrypted files are correct")
            print("   - Copy to your questions directory if needed")
            print("   - Delete encrypted files if no longer needed")
    else:
        print("[WARNING] Some files failed to decrypt. Check the error messages above.")
        print("   This usually indicates an incorrect password.")

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