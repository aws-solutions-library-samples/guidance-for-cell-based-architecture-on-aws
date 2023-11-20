FROM --platform=linux/amd64 public.ecr.aws/docker/library/python:3.11-slim
# https://gallery.ecr.aws/docker/library/python

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    && apt-get upgrade \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 9999 app \
  && useradd --uid 9999 --gid 9999 -m app
USER app
WORKDIR /cell

COPY requirements.txt .
RUN pip3 install -r requirements.txt --no-cache-dir

COPY app.py .

HEALTHCHECK --interval=1m --timeout=30s \
  CMD curl -f http://localhost:8080/ || exit 1
CMD [ "python3", "-m" , "flask", "run", "--host=0.0.0.0", "--port=8080"]
