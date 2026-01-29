# Configuration for Invoice Extraction System

# Ollama Configuration
OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llava:7b"  # Vision model for invoice extraction
OLLAMA_TIMEOUT = 120  # seconds

# PDF Processing Configuration
PDF_RESOLUTION = 200  # DPI for image conversion
MAX_PDF_SIZE = 50  # MB

# API Configuration
API_HOST = "0.0.0.0"
API_PORT = 8000
API_DEBUG = False

# Logging
LOG_LEVEL = "INFO"
LOG_FILE = "invoice_extraction.log"
