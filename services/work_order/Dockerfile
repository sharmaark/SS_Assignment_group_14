FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY services/work_order/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/requirements.txt

COPY services /app/services

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "services.work_order.src.api:app", "--host", "0.0.0.0", "--port", "8001"]
