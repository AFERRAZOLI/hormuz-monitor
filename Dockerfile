FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hormuz_monitor/ hormuz_monitor/
COPY start.py .

CMD ["python", "start.py"]
