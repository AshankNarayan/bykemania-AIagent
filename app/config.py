import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

BYKEMANIA_API_BASE = os.getenv("BYKEMANIA_API_BASE", "https://bykemania.com/agent/api")
MODEL_UTILISATION_ENDPOINT = os.getenv("MODEL_UTILISATION_ENDPOINT", "/model-utilisation")

MODELS_CSV_PATH = "app/data/models.csv"
LOCATIONS_CSV_PATH = "app/data/locations.csv"

GROQ_MODEL = "llama-3.3-70b-versatile"
OPENAI_FALLBACK_MODEL = "gpt-4o-mini"