FROM mcr.microsoft.com/playwright/python:v1.64.0-noble
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && playwright install chromium
COPY server.py ./
COPY static ./static
RUN useradd -m sahab && mkdir -p /app/data && chown -R sahab /app
USER sahab
EXPOSE 8800
VOLUME ["/app/data"]
CMD ["python", "server.py", "--host", "0.0.0.0", "--port", "8800", "--locale", "ar-EG"]
