FROM python:3.11-slim

WORKDIR /app

COPY backend ./backend
COPY README.md ./README.md

RUN pip install --no-cache-dir fastapi uvicorn

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
