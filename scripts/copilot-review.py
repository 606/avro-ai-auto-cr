#!/usr/bin/env python3
"""
GitHub Copilot Code Review for pre-commit hooks
Optimized for .NET Cloud Engineer workflow
"""

import os
import sys
import json
import requests
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

class CopilotReviewer:
    def __init__(self):
        self.copilot_url = os.getenv('COPILOT_PROXY_URL', 'http://localhost:8080/v1/chat/completions')
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load configuration from .copilot-config.json"""
        config_file = Path('.copilot-config.json')
        if config_file.exists():
            with open(config_file) as f:
                return json.load(f)

        return {
            "model": "gpt-4",
            "temperature": 0.2,
            "max_tokens": 1500,
            "critical_patterns": [
                r"security|auth|encrypt|decrypt|password|token",
                r"sql|database|query|injection",
                r"async|await|task|thread",
                r"memory|dispose|using|gc"
            ],
            "skip_patterns": [
                r"^using\s+",
                r"^\s*//.*$",
                r"^\s*\[.*\]\s*$"
            ]
        }

    def get_file_diff(self, filepath: str) -> Optional[str]:
        """Get diff for file"""
        try:
            # Get staged diff
            result = subprocess.run([
                'git', 'diff', '--cached', '--', filepath
            ], capture_output=True, text=True)

            return result.stdout if result.returncode == 0 else None
        except Exception as e:
            print(f"Error getting diff for {filepath}: {e}")
            return None

    def is_critical_change(self, diff: str, filepath: str) -> bool:
        """Determine if file requires critical review"""
        import re

        # Check critical patterns
        for pattern in self.config['critical_patterns']:
            if re.search(pattern, diff, re.IGNORECASE):
                return True

        # Large changes are always critical
        added_lines = len([line for line in diff.split('\n') if line.startswith('+')])
        removed_lines = len([line for line in diff.split('\n') if line.startswith('-')])

        return (added_lines + removed_lines) > 20

    def should_skip_review(self, diff: str) -> bool:
        """Should skip trivial changes"""
        import re

        meaningful_lines = [
            line for line in diff.split('\n')
            if line.startswith('+') or line.startswith('-')
        ]

        if len(meaningful_lines) < 3:
            for pattern in self.config['skip_patterns']:
                if all(re.match(pattern, line[1:].strip()) for line in meaningful_lines):
                    return True

        return False

    def review_file(self, filepath: str) -> Optional[Dict]:
        """Review individual file"""
        diff = self.get_file_diff(filepath)

        # If no git diff, read file content directly for testing
        if not diff:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                if content.strip():
                    diff = f"New file: {filepath}\n" + "\n".join([f"+{line}" for line in content.split('\n')])
            except Exception as e:
                print(f"Error reading file {filepath}: {e}")
                return None

        if not diff or self.should_skip_review(diff):
            return None

        system_prompt = f"""You are an experienced .NET Cloud Engineer.
Analyze code changes and provide:

1. **DECISION**: ACCEPT/REJECT (Score: 0-100)
2. **CRITICAL ISSUES**: Security, performance, bugs
3. **RECOMMENDATIONS**: Specific improvements

Focus: .NET best practices, SOLID, security, performance.
Format: Concise Markdown."""

        user_prompt = f"""**File**: {filepath}

```

{diff[:3000]}

```

Analyze the changes."""

        try:
            response = requests.post(self.copilot_url,
                json={
                    "model": self.config["model"],
                    "temperature": self.config["temperature"],
                    "max_tokens": self.config["max_tokens"],
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ]
                },
                timeout=30
            )

            if response.status_code == 200:
                try:
                    result = response.json()
                    review_text = result['choices'][0]['message']['content']

                    return {
                        'file': filepath,
                        'review': review_text,
                        'critical': self.is_critical_change(diff, filepath),
                        'diff_size': len(diff)
                    }
                except (KeyError, ValueError) as json_error:
                    print(f"[WARNING] Copilot API returned invalid JSON for {filepath}: {json_error}")
                    # Fall back to static analysis
                    return self._static_review(filepath, diff)
            else:
                print(f"[WARNING] Copilot API returned status {response.status_code} for {filepath}")
                return self._static_review(filepath, diff)

        except Exception as e:
            print(f"[WARNING] Copilot API error for {filepath}: {e}")
            # Fall back to static analysis
            return self._static_review(filepath, diff)

    def _static_review(self, filepath: str, diff: str) -> Dict:
        """Static code analysis fallback when AI API is unavailable"""
        import re

        issues = []
        score = 100

        # Security checks
        security_patterns = [
            (r'hashlib\.md5|hashlib\.sha1', 'Weak hashing algorithm detected', 30),
            (r'SELECT.*\+.*|INSERT.*\+.*', 'Potential SQL injection vulnerability', 40),
            (r'eval\s*\(|exec\s*\(', 'Dangerous code execution function', 50),
            (r'open\s*\([^)]*[\'"][rwa][\'"]\s*\)', 'File opened without context manager', 10),
        ]

        # Performance checks
        performance_patterns = [
            (r'for.*in.*range.*\n.*\+\s*=', 'Inefficient string concatenation in loop', 15),
            (r'time\.sleep\(\s*[0-9]+\s*\)', 'Blocking sleep operation', 10),
        ]

        all_patterns = security_patterns + performance_patterns

        for pattern, message, penalty in all_patterns:
            if re.search(pattern, diff, re.MULTILINE | re.IGNORECASE):
                issues.append(f"- {message}")
                score -= penalty

        critical = score < 70 or any('injection' in issue or 'dangerous' in issue.lower() for issue in issues)

        if issues:
            decision = "REJECT" if critical else "ACCEPT"
            review_text = f"""## Static Code Review Results

**DECISION**: {decision} (Score: {score}/100)

**ISSUES FOUND**:
{chr(10).join(issues)}

**RECOMMENDATIONS**:
- Use secure hashing algorithms (SHA-256 or better)
- Use parameterized queries to prevent SQL injection
- Use context managers for file operations
- Optimize string operations using join() or f-strings
- Consider async operations for I/O bound tasks

*Note: This is a static analysis fallback. For comprehensive AI-powered review, ensure copilot-proxy is properly configured.*"""
        else:
            review_text = f"""## Static Code Review Results

**DECISION**: ACCEPT (Score: {score}/100)

**STATUS**: No critical issues detected in static analysis.

**RECOMMENDATIONS**:
- Continue following best practices
- Consider adding comprehensive tests
- Ensure proper error handling

*Note: This is a static analysis fallback. For comprehensive AI-powered review, ensure copilot-proxy is properly configured.*"""

        return {
            'file': filepath,
            'review': review_text,
            'critical': critical,
            'diff_size': len(diff)
        }

    def save_review(self, reviews: List[Dict]):
        """Save review results"""
        reviews_dir = Path('.pre-commit-reviews')
        reviews_dir.mkdir(exist_ok=True)

        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

        review_file = reviews_dir / f"review_{timestamp}.md"

        with open(review_file, 'w') as f:
            f.write("# Pre-commit Code Review\n\n")
            f.write(f"**Timestamp**: {datetime.datetime.now().isoformat()}\n")
            f.write(f"**Files**: {len(reviews)}\n\n")

            for review in reviews:
                f.write(f"## File: {review['file']}\\n\\n")
                f.write(f"**Critical**: {'YES' if review['critical'] else 'NO'}\\n\\n")
                f.write(review['review'])
                f.write("\n\n---\n\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: copilot-review.py <file1> [file2] ...")
        return 0

    reviewer = CopilotReviewer()
    reviews = []
    failed_reviews = []

    print("[AI] Running GitHub Copilot Code Review...")

    for filepath in sys.argv[1:]:
        print(f"[REVIEW] Reviewing {filepath}...")

        review = reviewer.review_file(filepath)
        if review:
            reviews.append(review)

            # Show result in console
            print(f"[OK] {filepath}: {'[CRITICAL]' if review['critical'] else '[NORMAL]'}")

            # Check for REJECT
            if 'REJECT' in review['review'] or 'ВІДХИЛИТИ' in review['review']:
                failed_reviews.append(review)
        else:
            print(f"[SKIP] {filepath}: Skipped (trivial changes)")

    if reviews:
        reviewer.save_review(reviews)
        print(f"[SAVE] Review saved to .pre-commit-reviews/")

    if failed_reviews:
        print(f"\n[REJECT] {len(failed_reviews)} files REJECTED by review:")
        for review in failed_reviews:
            print(f"   - {review['file']}")
        return 1

    print(f"[PASS] All {len(reviews)} files passed review")
    return 0

if __name__ == '__main__':
    sys.exit(main())
