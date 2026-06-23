FROM python:3.11-slim

WORKDIR /app

# System deps (none strictly needed, but ensures clean pip)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps first for better Docker layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the full app
COPY bot.py .
COPY flags.py .
# Assets are not required for the bot to run, but copy anyway so they're
# available in the image for the /setuserpic workflow.
COPY assets/ ./assets/

ENV TELEGRAM_BOT_TOKEN=""
ENV PYTHONUNBUFFERED=1

# Sanity check at build time: ensure all modules import cleanly.
# This fails the build (with a clear error) if flags.py or any other
# module is missing or broken, instead of crashing at container start.
RUN python -c "import flags; import telegram; import deep_translator; import requests; print('build import-check OK')"

CMD ["python", "bot.py"]