FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

ARG INSTALL_LOCAL_AI=0
ARG INSTALL_OCR=1
ARG INSTALL_DEV=0

COPY . /app

RUN set -eux; \
  for attempt in 1 2 3 4 5; do \
    apt-get -o Acquire::Retries=5 update && \
    apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
      antiword \
      libreoffice-calc \
      libreoffice-writer \
      openssl \
      tesseract-ocr \
      tesseract-ocr-eng \
      tesseract-ocr-rus && \
    rm -rf /var/lib/apt/lists/* && \
    break; \
    if [ "$attempt" = "5" ]; then \
      echo "apt-get failed after 5 attempts" >&2; \
      exit 100; \
    fi; \
    echo "apt-get failed on attempt ${attempt}; retrying in 10 seconds" >&2; \
    rm -rf /var/lib/apt/lists/*; \
    sleep 10; \
  done

RUN extras="" \
  && if [ "$INSTALL_LOCAL_AI" = "1" ]; then extras="local-ai"; fi \
  && if [ "$INSTALL_OCR" = "1" ]; then extras="${extras:+$extras,}ocr"; fi \
  && if [ "$INSTALL_DEV" = "1" ]; then extras="${extras:+$extras,}dev"; fi \
  && if [ -n "$extras" ]; then pip install --no-cache-dir ".[${extras}]"; else pip install --no-cache-dir .; fi

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
