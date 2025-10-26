#!/usr/bin/env python3
"""
Cleanup script to remove debug statements and unnecessary code from the codebase.
"""
import os
import re
from pathlib import Path

# Files to process (exclude venv, __pycache__, migrations)
BASE_DIR = Path(__file__).parent.parent

# Patterns to remove or replace
PATTERNS = [
    # Remove debug print statements
    (r'print\(f?"DEBUG:.*?"\)', ''),
    (r'print\(f?"DEBUG.*?\)', ''),
    (r'print\("DEBUG.*?\)', ''),
    # Remove empty lines left behind
    (r'\n\s*\n\s*\n+', '\n\n'),
]

# Files to skip
SKIP_DIRS = ['__pycache__', '.git', 'migrations', 'instance', 'venv', '.venv', 'node_modules']

def should_skip_path(file_path):
    """Check if a path should be skipped"""
    parts = file_path.parts
    for skip_dir in SKIP_DIRS:
        if skip_dir in parts:
            return True
    return False

def process_file(file_path):
    """Process a single file to remove debug statements"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply patterns
        for pattern, replacement in PATTERNS:
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
        
        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Main cleanup function"""
    files_processed = 0
    files_modified = 0
    
    # Process Python files
    for python_file in BASE_DIR.rglob('*.py'):
        if should_skip_path(python_file):
            continue
        
        files_processed += 1
        if process_file(python_file):
            files_modified += 1
            print(f"Modified: {python_file}")
    
    print(f"\nProcessed {files_processed} files, modified {files_modified} files")

if __name__ == '__main__':
    main()
