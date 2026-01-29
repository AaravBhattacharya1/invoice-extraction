# Quick Start Guide

## 5-Minute Setup

### Step 1: Install Ollama

1. Download from https://ollama.com
2. Install for your OS (Windows, macOS, Linux)

### Step 2: Download the Vision Model

Open terminal and run:
```bash
ollama pull llava:7b
```

### Step 3: Start Ollama Service

Keep this running in a separate terminal:
```bash
ollama serve
```

### Step 4: Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 5: Run the Application

```bash
python main.py
```

You'll see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 6: Open in Browser

Go to: **http://localhost:8000**

You should see a "Upload PDF" form.

### Step 7: Test

1. Click "Choose File" and select your invoice PDF
2. Click "Extract Invoices"
3. Wait for processing (first time may take 30-60 seconds)
4. View results as formatted tables

## What's Happening

- **Stage 1**: PDF is split into pages
- **Stage 2**: Ollama's Llava vision model reads each page
- **Stage 3**: Invoices are merged and deduplicated
- **Stage 4**: Results formatted as Markdown tables

## Troubleshooting

**"Could not connect to Ollama"**
- Make sure `ollama serve` is running in another terminal

**Slow Processing**
- First invoice extraction takes longer (model warming up)
- CPU mode is slower than GPU; consider GPU if available

**Missing Fields in Extraction**
- If certain fields aren't extracted, it may need Ollama model fine-tuning
- Adjust the extraction prompt in `invoice_processor.py`

