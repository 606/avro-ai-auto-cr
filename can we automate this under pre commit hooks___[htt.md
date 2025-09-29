<img src="https://r2cdn.perplexity.ai/pplx-full-logo-primary-dark%402x.png" style="height:64px;margin-right:32px"/>

# can we automate this under pre commit hooks?

[https://pre-commit.com/](https://pre-commit.com/)

Так, ми можемо **повністю автоматизувати code review під pre-commit hooks**! Це набагато ефективніше ніж моніторинг через n8n.[^1]

Ось **оптимізований підхід** з використанням pre-commit:

```yaml
# .pre-commit-config.yaml
repos:
  # Стандартні перевірки
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.6.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-json

  # Локальні хуки для AI code review
  - repo: local
    hooks:
      # GitHub Copilot Code Review
      - id: copilot-review
        name: GitHub Copilot Code Review
        entry: ./scripts/copilot-review.py
        language: python
        stages: [pre-commit]
        types: [file]
        files: \.(cs|js|ts|py|sql)$
        exclude: |
          (?x)^(
            bin/|
            obj/|
            node_modules/|
            \.git/|
            Migrations/.*\.cs$|
            .*\.Designer\.cs$
          )
        pass_filenames: true
        require_serial: true
        additional_dependencies:
          - requests
          - gitpython
        
      # Batch Review для великих змін
      - id: batch-copilot-review
        name: Batch Copilot Review (Large Changes)
        entry: ./scripts/batch-review.py
        language: python
        stages: [pre-push]
        types: [file]
        files: \.(cs|js|ts)$
        pass_filenames: true
        args: [--threshold=10, --priority=high]
        additional_dependencies:
          - requests
          - gitpython

      # Smart Review Decision
      - id: smart-review
        name: Smart Review Filter
        entry: ./scripts/smart-filter.py
        language: python
        stages: [pre-commit]
        files: \.(cs|razor|js|ts|sql)$
        pass_filenames: true
        additional_dependencies:
          - gitpython
```


## 📝 Scripts Implementation

### `scripts/copilot-review.py`

```python
#!/usr/bin/env python3
"""
GitHub Copilot Code Review для pre-commit hooks
Оптимізовано для .NET Cloud Engineer workflow
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
        """Завантаження конфігурації з .copilot-config.json"""
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
        """Отримання diff для файлу"""
        try:
            # Отримуємо staged diff
            result = subprocess.run([
                'git', 'diff', '--cached', '--', filepath
            ], capture_output=True, text=True)
            
            return result.stdout if result.returncode == 0 else None
        except Exception as e:
            print(f"Error getting diff for {filepath}: {e}")
            return None

    def is_critical_change(self, diff: str, filepath: str) -> bool:
        """Визначення чи потребує файл критичного ревью"""
        import re
        
        # Перевірка критичних паттернів
        for pattern in self.config['critical_patterns']:
            if re.search(pattern, diff, re.IGNORECASE):
                return True
                
        # Великі зміни завжди критичні
        added_lines = len([line for line in diff.split('\n') if line.startswith('+')])
        removed_lines = len([line for line in diff.split('\n') if line.startswith('-')])
        
        return (added_lines + removed_lines) > 20

    def should_skip_review(self, diff: str) -> bool:
        """Чи слід пропустити тривіальні зміни"""
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
        """Ревью окремого файлу"""
        diff = self.get_file_diff(filepath)
        if not diff or self.should_skip_review(diff):
            return None
            
        system_prompt = f"""Ви - досвідчений .NET Cloud Engineer. 
Проаналізуйте зміни коду та надайте:

1. **РІШЕННЯ**: ПРИЙНЯТИ/ВІДХИЛИТИ (Оцінка: 0-100)
2. **КРИТИЧНІ ПРОБЛЕМИ**: Безпека, продуктивність, баги
3. **РЕКОМЕНДАЦІЇ**: Конкретні покращення

Фокус: .NET best practices, SOLID, безпека, продуктивність.
Формат: Лаконічний Markdown."""

        user_prompt = f"""**Файл**: {filepath}

```

{diff[:3000]}

```

Проаналізуйте зміни."""

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
                result = response.json()
                review_text = result['choices'][^0]['message']['content']
                
                return {
                    'file': filepath,
                    'review': review_text,
                    'critical': self.is_critical_change(diff, filepath),
                    'diff_size': len(diff)
                }
                
        except Exception as e:
            print(f"⚠️  Copilot API error for {filepath}: {e}")
            
        return None

    def save_review(self, reviews: List[Dict]):
        """Збереження результатів ревью"""
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
                f.write(f"## 📄 {review['file']}\n\n")
                f.write(f"**Critical**: {'🔴 Yes' if review['critical'] else '🟢 No'}\n\n")
                f.write(review['review'])
                f.write("\n\n---\n\n")

def main():
    if len(sys.argv) < 2:
        print("Usage: copilot-review.py <file1> [file2] ...")
        return 0
        
    reviewer = CopilotReviewer()
    reviews = []
    failed_reviews = []
    
    print("🤖 Running GitHub Copilot Code Review...")
    
    for filepath in sys.argv[1:]:
        print(f"📄 Reviewing {filepath}...")
        
        review = reviewer.review_file(filepath)
        if review:
            reviews.append(review)
            
            # Показуємо результат в консолі
            print(f"✅ {filepath}: {'🔴 Critical' if review['critical'] else '🟢 Normal'}")
            
            # Перевіряємо на ВІДХИЛИТИ
            if 'ВІДХИЛИТИ' in review['review'] or 'REJECT' in review['review']:
                failed_reviews.append(review)
        else:
            print(f"⏭️  {filepath}: Skipped (trivial changes)")
    
    if reviews:
        reviewer.save_review(reviews)
        print(f"💾 Review saved to .pre-commit-reviews/")
    
    if failed_reviews:
        print(f"\n🚫 {len(failed_reviews)} files REJECTED by review:")
        for review in failed_reviews:
            print(f"   - {review['file']}")
        return 1
    
    print(f"✅ All {len(reviews)} files passed review")
    return 0

if __name__ == '__main__':
    sys.exit(main())
```


### `scripts/smart-filter.py`

```python
#!/usr/bin/env python3
"""
Smart Review Filter - визначає які файли потребують детального ревью
"""

import sys
import subprocess
import re
from pathlib import Path

def get_file_complexity(filepath: str) -> int:
    """Оцінка складності файлу для ревью"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Складність базується на:
        complexity = 0
        
        # Кількість методів/функцій
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
    """Фільтр файлів за складністю"""
    threshold = 10  # мінімальна складність для ревью
    
    for filepath in sys.argv[1:]:
        complexity = get_file_complexity(filepath)
        
        if complexity >= threshold:
            print(f"🔍 {filepath} (complexity: {complexity})")
        else:
            print(f"⏭️  {filepath} (complexity: {complexity}) - SKIPPED")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
```


### `.copilot-config.json`

```json
{
  "model": "gpt-4",
  "temperature": 0.2,
  "max_tokens": 1500,
  "critical_patterns": [
    "security|auth|encrypt|decrypt|password|token|jwt",
    "sql|database|query|injection|connection|transaction", 
    "async|await|task|thread|parallel|concurrent",
    "memory|dispose|using|gc|finalizer|destructor",
    "controller|service|repository|entity|model",
    "cache|session|cookie|cors|csrf"
  ],
  "skip_patterns": [
    "^using\\s+",
    "^\\s*//.*$", 
    "^\\s*\\[.*\\]\\s*$",
    "^\\s*namespace\\s+",
    "^\\s*{\\s*}\\s*$"
  ],
  "file_extensions": [".cs", ".js", ".ts", ".sql", ".razor"],
  "priority_files": [
    "*Controller.cs",
    "*Service.cs", 
    "*Repository.cs",
    "*.sql",
    "appsettings*.json"
  ]
}
```


## 🚀 Setup Instructions

### 1. Встановлення pre-commit:

```bash
# macOS/Linux
pip install pre-commit

# Windows  
pip install pre-commit

# Альтернативно через brew (macOS)
brew install pre-commit
```


### 2. Налаштування в проекті:

```bash
# В корені репозиторію
mkdir scripts
chmod +x scripts/*.py

# Встановлення хуків
pre-commit install

# Перший запуск на всіх файлах
pre-commit run --all-files
```


### 3. GitHub Copilot Proxy:

```bash
npm install -g copilot-proxy
gh auth login
copilot-proxy --port 8080
```


## ✨ Переваги цього підходу:

### ⚡ **Performance**

- **Локальне виконання** - без затримок мережі
- **Smart filtering** - пропуск тривіальних змін
- **Batch processing** - ефективне використання API[^1]


### 🛡️ **Integration**

- **Автоматичний запуск** на кожен commit/push
- **Блокування** коммітів з критичними помилками
- **IDE інтеграція** через pre-commit[^2]


### 🔧 **Flexibility**

- **Конфігурування** через `.copilot-config.json`
- **Різні stages** - pre-commit, pre-push, pre-merge
- **Exclude patterns** - ігнорування генерованих файлів

Цей підхід **набагато ефективніший** ніж n8n workflow, оскільки працює безпосередньо в Git workflow і не потребує зовнішнього сервера.[^1]

<div align="center">⁂</div>

[^1]: https://pre-commit.com

[^2]: image.jpg

