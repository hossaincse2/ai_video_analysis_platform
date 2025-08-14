import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://username:password@localhost/ai_video_platform")

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# File paths
BASE_DIR = Path(__file__).resolve().parent
DOWNLOADS_DIR = BASE_DIR / "downloads"
UPLOADS_DIR = BASE_DIR / "uploads"

# Create directories
DOWNLOADS_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)

# Validate required environment variables
if not OPENAI_API_KEY:
    print("Warning: OPENAI_API_KEY not set. AI features will not work.")

if "postgresql://" not in DATABASE_URL:
    print("Warning: DATABASE_URL may not be configured properly.")