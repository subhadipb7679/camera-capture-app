FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY static ./static
RUN useradd --create-home --uid 10001 appuser \
    && mkdir /app/captures && chown appuser:appuser /app/captures
USER appuser
ENV CAPTURE_STORAGE_DIR=/app/captures
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers"]
