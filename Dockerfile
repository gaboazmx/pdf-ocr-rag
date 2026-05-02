# ============================================================
# PDF OCR → Markdown  |  Sistema RAG Jurídico
# Base: Python 3.11 slim + Tesseract + Poppler
# ============================================================
FROM python:3.11-slim

# Instalar Tesseract + idiomas + Poppler (para pdf2image)
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-spa \
    tesseract-ocr-eng \
    tesseract-ocr-fra \
    tesseract-ocr-por \
    poppler-utils \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    && rm -rf /var/lib/apt/lists/*

# Directorio de trabajo
WORKDIR /app

# Dependencias Python primero (capa cacheada)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código de la app
COPY . .

# Crear carpetas temporales
RUN mkdir -p /tmp/ocr_uploads /tmp/ocr_outputs

# Puerto
EXPOSE 5000

# Comando de inicio (Render usa la env var PORT)
CMD gunicorn app:app \
    --bind 0.0.0.0:${PORT:-5000} \
    --workers 1 \
    --threads 4 \
    --timeout 300 \
    --worker-class sync \
    --access-logfile - \
    --error-logfile -
