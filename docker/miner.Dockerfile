FROM python:3.11-slim

# Rust toolchain for building engram-core
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl build-essential pkg-config libssl-dev git \
    && curl https://sh.rustup.rs -sSf | sh -s -- -y --default-toolchain stable \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

# Install maturin for building PyO3 extension
RUN pip install --no-cache-dir maturin

# Copy Rust crate and build it
COPY engram-core/ ./engram-core/
COPY Cargo.toml ./
RUN cd engram-core && maturin build --release && \
    pip install --no-cache-dir target/wheels/*.whl

# Install Python dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY engram/ ./engram/
COPY neurons/ ./neurons/
COPY data/ ./data/

# Create data dir for FAISS index persistence
RUN mkdir -p /app/data

EXPOSE 8091

# Env comes from docker-compose env_file (.env.miner) — never baked in.
CMD ["python", "neurons/miner.py"]
