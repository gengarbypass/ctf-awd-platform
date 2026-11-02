FROM python:3.12-slim

ARG PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir --index-url "$PIP_INDEX_URL" -r requirements.txt
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN groupadd --system --gid 10001 awd \
    && useradd --system --uid 10001 --gid awd --no-create-home awd \
    && chown -R awd:awd /app
USER awd
EXPOSE 8000 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
