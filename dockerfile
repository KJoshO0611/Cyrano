FROM python:3.11-slim

WORKDIR /app


# Install Python dependencies first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set permissions
RUN chmod -R 755 /app

# Run the bot
CMD ["python", "bot.py"]