FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

ARG INSTALL_LOCAL_AI=0
ARG INSTALL_OCR=1

COPY . /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus \
  && rm -rf /var/lib/apt/lists/*

RUN extras="" \
  && if [ "$INSTALL_LOCAL_AI" = "1" ]; then extras="local-ai"; fi \
  && if [ "$INSTALL_OCR" = "1" ]; then extras="${extras:+$extras,}ocr"; fi \
  && if [ -n "$extras" ]; then pip install --no-cache-dir ".[${extras}]"; else pip install --no-cache-dir .; fi

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
