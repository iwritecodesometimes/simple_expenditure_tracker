FROM python:3.11-slim

WORKDIR /app

# CPU-only PyTorch: several GB smaller than the default build, and the bot doesn't need a GPU.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download the categorisation model now, so the bot starts quickly and works offline.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

# Custom categories and training results live here. Mount a volume on it to keep them
# (docker-compose.yml does this; on Railway, attach a volume at /app/data).
ENV DATA_DIR=/app/data

CMD ["python", "bot.py"]
