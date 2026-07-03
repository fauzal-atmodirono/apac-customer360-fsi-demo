# ADK "Ask the data" agent — Cloud Run service.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

ENV PORT=8080 \
    GOOGLE_GENAI_USE_VERTEXAI=TRUE

# uvicorn honours $PORT provided by Cloud Run.
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT}"]
