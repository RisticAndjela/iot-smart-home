FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Kopiraj requirements i instaliraj (očekuje frontend/requirements.txt)
COPY frontend/requirements.txt /app/frontend/requirements.txt
RUN pip install --upgrade pip \
    && pip install -r /app/frontend/requirements.txt \
    && rm -rf /root/.cache/pip

COPY . /app

WORKDIR /app/frontend

EXPOSE 5000

CMD ["python", "app.py"]