FROM python:3.12-slim
WORKDIR /orange
COPY requirements-g3x.txt .
RUN pip install --no-cache-dir -r requirements-g3x.txt
COPY . .
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
CMD ["python", "-m", "app.runtime.http_api"]
