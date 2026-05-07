FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG INSTALL_LOCAL_AI=0

COPY . /app

RUN if [ "$INSTALL_LOCAL_AI" = "1" ]; then pip install --no-cache-dir ".[local-ai]"; else pip install --no-cache-dir .; fi

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
