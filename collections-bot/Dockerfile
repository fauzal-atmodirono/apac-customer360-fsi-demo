# Collections bot — Cloud Run service.
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Cloud Run injects $PORT (8080). Gemini runs on Vertex ADC (no key) via the
# runtime service account; BigQuery reads use the same identity.
ENV PORT=8080 \
    GOOGLE_GENAI_USE_VERTEXAI=TRUE

CMD ["sh", "-c", "uvicorn server:get_app --factory --host 0.0.0.0 --port ${PORT}"]
