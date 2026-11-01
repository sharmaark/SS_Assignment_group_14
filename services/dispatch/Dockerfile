FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/dispatch/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY services /app/services

EXPOSE 8003

CMD ["python", "-m", "uvicorn", "services.dispatch.src.api:app", "--host", "0.0.0.0", "--port", "8003"]
