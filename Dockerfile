FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hormuz_monitor/ hormuz_monitor/

ENV PORT=8000

EXPOSE ${PORT}

CMD ["sh", "-c", "uvicorn hormuz_monitor.server:app --host 0.0.0.0 --port ${PORT}"]
