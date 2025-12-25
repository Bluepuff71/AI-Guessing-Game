# LOOT RUN Multiplayer Server
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy game logic (reused from local game)
COPY game /app/game
COPY ai /app/ai
COPY config /app/config

# Copy server code
COPY server /app/server

# Set Python path to include app directory
ENV PYTHONPATH=/app:/app/server

WORKDIR /app/server

# Expose port
EXPOSE 8000

# Run the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
