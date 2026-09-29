FROM python:3.12-slim AS api
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY apps/api/requirements.lock.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY apps/api /app/apps/api
COPY data /app/data
RUN pip install --no-cache-dir --no-deps /app/apps/api && useradd --create-home reef
USER reef
EXPOSE 8000
CMD ["python", "-m", "reef.serve"]
