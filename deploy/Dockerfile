# The chat app image: Gradio UI + the shipped LangGraph agent + the 200-book catalog.
# Build it from this folder: docker build -t arabic-book-recommender .
# No keys inside: on AWS they arrive from Secrets Manager as environment variables.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GRADIO_ANALYTICS_ENABLED=False \
    PORT=8080

WORKDIR /app

# Dependencies first, so this layer is reused until requirements.txt changes.
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY bookrec/ bookrec/
COPY app/ app/
COPY data/catalog.csv data/catalog.csv

# Never run the app as root inside the container.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8080
CMD ["python", "-m", "app.main"]
