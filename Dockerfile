FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default demo date so seeded data looks alive
ENV CRM_TODAY=2026-07-20

RUN python -m app.seed --csv data/Grid_view.csv

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
