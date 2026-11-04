FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8501

WORKDIR /app

# requirements.txt installs this package via -e ., so metadata and src must exist.
COPY requirements.txt pyproject.toml README.md ./
COPY src/ ./src/
RUN python -m pip install --no-cache-dir -r requirements.txt \
    && useradd --create-home --uid 10001 app \
    && chown -R app:app /app

COPY --chown=app:app app.py ./app.py
USER app

EXPOSE 8501

# Resolve PORT at container startup; exec forwards termination to Streamlit.
CMD ["sh", "-c", "exec python -m streamlit run app.py --server.address=0.0.0.0 --server.port=\"${PORT:-8501}\" --server.headless=true --browser.gatherUsageStats=false"]
