#!/usr/bin/env python3
"""
Batch Review для великих змін - оптимізований для pre-push hooks
"""

import os
import sys
import json
import requests
import subprocess
from pathlib import Path
from typing import List, Dict, Optional
import argparse

class BatchReviewer:
    def __init__(self):
        self.copilot_url = os.getenv('COPILOT_PROXY_URL', 'http://localhost:8080/v1/chat/completions')
        self.config = self._load_config()
        
    def _load_config(self) -> Dict:
        """Завантаження конфігурації"""
        config_file = Path('.copilot-config.json')
        if config_file.exists():
            with open(config_file) as f:
                return json.load(f)
        
        return {
            "model": "gpt-4",
            "temperature": 0.2,
            "max_tokens": 2000,
            "batch_size": 5
        }

    def get_changed_files(self) -> List[str]:
        """Отримання списку змінених файлів"""
        try:
            # Отримуємо файли що будуть push'нуті
            result = subprocess.run([
                'git', 'diff', '--name-only', 'HEAD~1', 'HEAD'
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                return [f.strip() for f in result.stdout.split('\n') if f.strip()]
            else:
                # Fallback - staged files
                result = subprocess.run([
                    'git', 'diff', '--cached', '--name-only'
                ], capture_output=True, text=True)
                return [f.strip() for f in result.stdout.split('\n') if f.strip()]
                
        except Exception as e:
            print(f"Error getting changed files: {e}")
            return []

    def batch_review(self, files: List[str], priority: str = "normal") -> Optional[Dict]:
        """Батч ревью декількох файлів"""
        if not files:
            return None
            
        # Збираємо всі diff'и
        combined_diff = ""
        for filepath in files:
            try:
                result = subprocess.run([
                    'git', 'diff', '--cached', '--', filepath
                ], capture_output=True, text=True)
                
                if result.returncode == 0 and result.stdout:
                    combined_diff += f"\n\n### {filepath}\n{result.stdout}"
            except Exception as e:
                print(f"Error getting diff for {filepath}: {e}")

        if not combined_diff.strip():
            return None

        system_prompt = f"""Ви - Lead .NET Cloud Engineer що проводить code review.
Проаналізуйте ВЕСЬ набір змін як цілісну feature/bugfix.

**ПРІОРИТЕТ**: {priority.upper()}

Надайте:
1. **ЗАГАЛЬНЕ РІШЕННЯ**: ПРИЙНЯТИ/ВІДХИЛИТИ (0-100)
2. **АРХІТЕКТУРНІ ПРОБЛЕМИ**: Загальні проблеми дизайну
3. **МІЖФАЙЛОВІ ЗВ'ЯЗКИ**: Консистентність між файлами
4. **РИЗИКИ**: Потенційні проблеми при деплої

Формат: Структурований Markdown з чіткими рекомендаціями."""

        user_prompt = f"""**Batch Review** ({len(files)} файлів)

**Файли**: {', '.join(files)}

```diff
{combined_diff[:8000]}  
```

Проаналізуйте як цілісну зміну."""

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
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                review_text = result['choices'][0]['message']['content']
                
                return {
                    'files': files,
                    'review': review_text,
                    'priority': priority,
                    'total_files': len(files)
                }
                
        except Exception as e:
            print(f"⚠️  Batch review API error: {e}")
            
        return None

    def save_batch_review(self, review: Dict):
        """Збереження batch review"""
        reviews_dir = Path('.pre-commit-reviews')
        reviews_dir.mkdir(exist_ok=True)
        
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        
        review_file = reviews_dir / f"batch_review_{timestamp}.md"
        
        with open(review_file, 'w') as f:
            f.write("# Batch Code Review (Pre-Push)\n\n")
            f.write(f"**Timestamp**: {datetime.datetime.now().isoformat()}\n")
            f.write(f"**Priority**: {review['priority'].upper()}\n")
            f.write(f"**Files Count**: {review['total_files']}\n\n")
            f.write(f"**Files**:\n")
            for file in review['files']:
                f.write(f"- {file}\n")
            f.write("\n")
            f.write("## Review Results\n\n")
            f.write(review['review'])
            f.write("\n")

def main():
    parser = argparse.ArgumentParser(description='Batch Code Review for Pre-Push')
    parser.add_argument('--threshold', type=int, default=10, 
                       help='Minimum number of files to trigger batch review')
    parser.add_argument('--priority', choices=['low', 'normal', 'high'], default='normal',
                       help='Review priority level')
    parser.add_argument('files', nargs='*', help='Files to review (optional)')
    
    args = parser.parse_args()
    
    reviewer = BatchReviewer()
    
    # Використовуємо передані файли або отримуємо автоматично
    files = args.files if args.files else reviewer.get_changed_files()
    
    # Фільтруємо тільки потрібні розширення
    relevant_extensions = ['.cs', '.js', '.ts', '.py', '.sql', '.razor', '.json']
    files = [f for f in files if any(f.endswith(ext) for ext in relevant_extensions)]
    
    if len(files) < args.threshold:
        print(f"⏭️  Only {len(files)} files changed (threshold: {args.threshold}) - SKIPPED")
        return 0
    
    print(f"🔍 Running batch review on {len(files)} files (priority: {args.priority})...")
    
    # Розбиваємо на батчі якщо забагато файлів
    batch_size = reviewer.config.get('batch_size', 5)
    failed_reviews = []
    
    for i in range(0, len(files), batch_size):
        batch_files = files[i:i+batch_size]
        print(f"📦 Reviewing batch {i//batch_size + 1}: {len(batch_files)} files...")
        
        review = reviewer.batch_review(batch_files, args.priority)
        if review:
            reviewer.save_batch_review(review)
            
            # Перевіряємо на rejection
            if 'ВІДХИЛИТИ' in review['review'] or 'REJECT' in review['review']:
                failed_reviews.extend(batch_files)
                print(f"🚫 Batch {i//batch_size + 1} REJECTED")
            else:
                print(f"✅ Batch {i//batch_size + 1} APPROVED")
        else:
            print(f"⚠️  Batch {i//batch_size + 1} - Review failed")
    
    if failed_reviews:
        print(f"\n🚫 {len(failed_reviews)} files REJECTED by batch review:")
        for file in failed_reviews:
            print(f"   - {file}")
        return 1
    
    print(f"✅ All {len(files)} files passed batch review")
    return 0

if __name__ == '__main__':
    sys.exit(main())