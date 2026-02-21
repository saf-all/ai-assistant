# SafAI - AI Code Assistant

ChatGPT-like AI assistant that understands your codebase. All conversations saved on your server.

## Features

- 🤖 **Code Understanding** - AI has access to your entire codebase
- 💬 **Chat Interface** - ChatGPT-like UI
- 💾 **Persistent Memory** - All conversations saved to SQLite
- 🔍 **Code Context** - Automatically indexes Python, JavaScript, HTML, CSS files
- 🔒 **Private** - Everything stored on your server
- 🆓 **FREE AI** - Uses OpenRouter free model

## Setup

```bash
cd ai-assistant
pip install -r requirements.txt
python app.py
```

Visit: http://localhost:5004

### Email Configuration

Add to `.env`:
```
OPENROUTER_API_KEY=your-key
SMTP_EMAIL=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

**Gmail Setup:**
1. Enable 2-Factor Authentication
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Use app password in `.env`

## Index Your Codebase

```bash
python index_codebase.py
```

This scans your project and indexes all code files so the AI can understand your codebase.

## Usage

1. Start the app
2. Run `index_codebase.py` to index your code
3. Login and start chatting
4. Ask questions about your code:
   - "Explain how the expense tracker works"
   - "How do I add a new route to the main app?"
   - "What database models do I have?"
   - "Help me debug this error..."

## Cloudflare Tunnel

Add to tunnel config:

```yaml
ingress:
  - hostname: ai.safalpanta.com
    service: http://localhost:5004
  - hostname: nas.safalpanta.com
    service: http://localhost:5003
  - hostname: terminal.safalpanta.com
    service: http://localhost:5002
  - hostname: expense.safalpanta.com
    service: http://localhost:5001
  - hostname: safalpanta.com
    service: http://localhost:5000
  - service: http_status:404
```

## Database

SQLite database (`ai_assistant.db`) stores:
- Conversations
- Messages (chat history)
- Code context (indexed files)

## Re-index Code

Run `index_codebase.py` whenever you update your code to keep the AI's knowledge current.
