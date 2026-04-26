FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data

ENV DATABASE_URL=sqlite:////data/8591.db

EXPOSE 8080

CMD ["python", "main.py", "start"]
