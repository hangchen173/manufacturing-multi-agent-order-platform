FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HF_HOME=/opt/huggingface

WORKDIR /app
COPY requirements.txt ./
# Use the CPU wheel explicitly. The default Linux resolver may select CUDA
# packages, which are unnecessary for this CPU-only deployment.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.2.2+cpu
RUN pip install --no-cache-dir -r requirements.txt

# Keep the embedding model in the image so first order processing is not blocked by a download.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1

COPY . ./
EXPOSE 5001
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
