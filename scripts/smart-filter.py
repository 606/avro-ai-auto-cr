#!/usr/bin/env python3
"""
Smart Review Filter - determines which files need detailed review
"""

import sys
import subprocess
import re
from pathlib import Path

def get_file_complexity(filepath: str) -> int:
    """Assess file complexity for review"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Complexity based on:
        complexity = 0

        # Number of methods/functions
        complexity += len(re.findall(r'\b(public|private|protected|internal)\s+\w+.*?\(', content)) * 2

        # SQL queries
        complexity += len(re.findall(r'(SELECT|INSERT|UPDATE|DELETE)', content, re.IGNORECASE)) * 3

        # Async/await patterns
        complexity += len(re.findall(r'\b(async|await)\b', content)) * 2

        # Linq queries
        complexity += len(re.findall(r'\.(Where|Select|FirstOrDefault|Any|All)\(', content)) * 1

        # Exception handling
        complexity += len(re.findall(r'\b(try|catch|throw)\b', content)) * 2

        return complexity

    except Exception:
        return 0

def main():
    """Filter files by complexity"""
    threshold = 10  # minimum complexity for review

    reviewed_files = []
    skipped_files = []

    for filepath in sys.argv[1:]:
        complexity = get_file_complexity(filepath)

        if complexity >= threshold:
            reviewed_files.append((filepath, complexity))
        else:
            skipped_files.append((filepath, complexity))

    # Only print summary to avoid duplication with main review
    if reviewed_files:
        print(f"[COMPLEXITY] {len(reviewed_files)} files need detailed review")
    if skipped_files:
        print(f"[COMPLEXITY] {len(skipped_files)} files skipped (low complexity)")

    return 0

if __name__ == '__main__':
    sys.exit(main())
