FROM python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS builder
RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY vendor/ vendor/
COPY scripts/install.py scripts/install.py
RUN python scripts/install.py && g++ --version > build/compiler.txt && dpkg-query -W > build/packages.txt
FROM python:3.14.7-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /app/build/gemm /app/build/gemm
COPY --from=builder /app/build/compiler.txt /app/build/packages.txt /app/build/
COPY service.py worker.py evidence.py ./
COPY scripts/validate.py scripts/install.py scripts/
COPY container/client.py container/client.py
RUN touch /app/readonly-probe && chown 10001:10001 /app/readonly-probe
USER 10001:10001
CMD ["python", "service.py", "--host", "0.0.0.0", "--port", "8080"]
FROM runtime AS fixture
COPY --chmod=0555 container/slow_worker.py /app/container/slow_worker.py
