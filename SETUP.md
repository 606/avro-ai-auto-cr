# AI-Powered Code Review Setup

This repository includes automated AI code review using GitHub Copilot integrated with pre-commit hooks.

## Prerequisites

1. **Python 3.7+** with pip
2. **Git** repository
3. **GitHub Copilot access** (optional - for live reviews)

## Quick Setup

### 1. Install Dependencies

```bash
# Install pre-commit
pip install pre-commit

# Install Python dependencies for AI scripts
pip install requests gitpython
```

### 2. Install Hooks

```bash
# Install pre-commit and pre-push hooks
pre-commit install --hook-type pre-commit --hook-type pre-push

# Test installation
pre-commit run --all-files
```

### 3. GitHub Copilot Integration (Optional)

For live AI reviews, set up Copilot proxy:

```bash
# First install GitHub CLI
# macOS (recommended - using Homebrew)
brew install gh

# Windows (using winget)
winget install --id GitHub.cli

# Windows: Add to PATH globally (run as Administrator)
# Add GitHub CLI to system PATH for all users
setx /M PATH "%PATH%;C:\Program Files\GitHub CLI"

# Or using Chocolatey
# choco install gh

# Or using Scoop
# scoop install gh

# After installation, restart PowerShell or run:
# $env:PATH += ";C:\Program Files\GitHub CLI"

# Install copilot-proxy (requires Node.js)
npm install -g copilot-proxy

# Authenticate with GitHub
gh auth login

# Start proxy server (set port via environment variable)
# Option 1: Set port and start
$env:PORT=8080; copilot-proxy

# Option 2: Alternative syntax
PORT=8080 copilot-proxy

# Option 3: Find and kill process on port 3000 first
# netstat -ano | findstr :3000
# taskkill /PID <PID> /F
# Then: copilot-proxy
```

Set environment variable (match the port you used above):
```bash
# Windows PowerShell (if using port 8080)
$env:COPILOT_PROXY_URL="http://localhost:8080/v1/chat/completions"

# Windows PowerShell (if using default port 3000)
$env:COPILOT_PROXY_URL="http://localhost:3000/v1/chat/completions"

# Windows Command Prompt
set COPILOT_PROXY_URL=http://localhost:8080/v1/chat/completions

# Linux/macOS
export COPILOT_PROXY_URL="http://localhost:8080/v1/chat/completions"
```

## Configuration

### `.copilot-config.json`
Configure AI review behavior:
- `critical_patterns`: Code patterns requiring detailed review
- `skip_patterns`: Patterns to skip (trivial changes)
- `file_extensions`: Supported file types
- `complexity_threshold`: Minimum complexity for review

### Pre-commit Hooks

**Pre-commit stage:**
- `copilot-review`: Individual file AI review
- `smart-review-filter`: Complexity-based filtering

**Pre-push stage:**
- `batch-copilot-review`: Batch review for large changes (5+ files)

## Usage

### Automatic (Recommended)
Reviews run automatically on:
- `git commit` - Individual files reviewed
- `git push` - Batch review if 5+ files changed

### Manual Testing
```bash
# Run all hooks on all files
pre-commit run --all-files

# Run specific hook
pre-commit run copilot-review --all-files

# Test batch review
python scripts/batch-review.py --threshold=1 file1.py file2.py
```

## Review Output

Reviews are saved to `.pre-commit-reviews/`:
- `review_YYYYMMDD_HHMMSS.md` - Individual reviews
- `batch_review_YYYYMMDD_HHMMSS.md` - Batch reviews

## Blocking Behavior

Commits/pushes are **blocked** if AI review returns:
- `REJECT` decision
- Critical security/performance issues identified

## File Extensions Supported

- `.cs` - C# files
- `.js`, `.ts` - JavaScript/TypeScript
- `.py` - Python files
- `.sql` - SQL queries
- `.json`, `.yml`, `.yaml` - Configuration files
- `.razor` - Razor templates

## Customization

Edit `.copilot-config.json` to adjust:
- Review sensitivity
- File patterns to include/exclude
- Complexity thresholds
- AI model parameters

## Troubleshooting

### GitHub CLI Not Found After Installation
1. **Restart PowerShell** - Close and reopen your terminal
2. **Add to current session**: `$env:PATH += ";C:\Program Files\GitHub CLI"`
3. **Add globally (as Administrator)**:
   ```powershell
   # Run PowerShell as Administrator, then:
   [Environment]::SetEnvironmentVariable("PATH", $env:PATH + ";C:\Program Files\GitHub CLI", [EnvironmentVariableTarget]::Machine)
   ```

### Copilot-proxy Port Issues
1. **Port 3000 already in use error**:
   ```powershell
   # Find what's using port 3000
   netstat -ano | findstr :3000

   # Kill the process (replace <PID> with actual process ID)
   taskkill /PID <PID> /F

   # Or use a different port
   $env:PORT=8080; copilot-proxy
   ```

2. **NPM global packages not in PATH**:
   ```powershell
   # Add npm global directory to PATH
   $env:PATH += ";C:\Users\$env:USERNAME\AppData\Roaming\npm"
   ```

### No AI Reviews Running
1. Check `COPILOT_PROXY_URL` environment variable
2. Verify copilot-proxy is running
3. Check GitHub authentication: `gh auth status`

### Python Import Errors
```bash
# Ensure dependencies installed in correct environment
pip install requests gitpython
```

### Permission Issues (Windows)
```bash
# Ensure scripts are executable
icacls scripts\*.py /grant Everyone:F
```

## Architecture

```
┌─────────────────┐    ┌──────────────┐    ┌─────────────────┐
│   Git Hooks     │───▶│   AI Scripts │───▶│  Review Output  │
│                 │    │              │    │                 │
│ • pre-commit    │    │ • Individual │    │ • .md reports   │
│ • pre-push      │    │ • Batch      │    │ • Block/Allow   │
│                 │    │ • Filtering  │    │                 │
└─────────────────┘    └──────────────┘    └─────────────────┘
```

This setup provides automated, intelligent code review that scales with your development workflow while maintaining code quality standards.
