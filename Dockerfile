FROM python:3.10-slim

WORKDIR /app

# Install system dependencies (फोर्स इंस्टॉल)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    gcc \
    g++ \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of the files
COPY . .

# Run bot
CMD ["python", "bot.py"]
