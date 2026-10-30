# Tenura — app + OCR engine
FROM python:3.12-slim

# Tesseract is needed for image (photo) OCR at runtime. PDF and text uploads
# work without it; installing it here means image uploads work too.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so this layer is cached when only code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Bind the port the platform routes to and health-checks. RumptyCloud injects
# the configured port as $PORT at runtime; fall back to 8080 so the image also
# runs unchanged locally. Hardcoding 8080 instead is the classic cause of a
# build that succeeds but a deployment that never becomes active.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
