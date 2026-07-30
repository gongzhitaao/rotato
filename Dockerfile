FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY rotato ./rotato
RUN pip install --no-cache-dir .

ENTRYPOINT ["python", "-m", "rotato"]
