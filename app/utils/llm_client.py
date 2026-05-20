from langchain_groq import ChatGroq
from app.config import GROQ_API_KEY, GROQ_MODEL

llm = ChatGroq(
    model=GROQ_MODEL,
    groq_api_key=GROQ_API_KEY,
    temperature=0.3,
    max_tokens=1024,
)