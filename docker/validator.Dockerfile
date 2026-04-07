FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential pkg-config libssl-dev git \
    && curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

RUN pip install --no-cache-dir maturin

COPY engram-core/ ./engram-core/
COPY Cargo.toml ./
RUN cd engram-core && maturin build --release && \
    pip install --no-cache-dir target/wheels/*.whl

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY engram/ ./engram/
COPY neurons/ ./neurons/
COPY data/ ./data/

# Create data dir for ground truth persistence
RUN mkdir -p /app/data

# Validator connects outbound to miners only — no public port needed.
# Env comes from docker-compose env_file (.env.validator) — never baked in.
CMD ["python", "neurons/validator.py"]
