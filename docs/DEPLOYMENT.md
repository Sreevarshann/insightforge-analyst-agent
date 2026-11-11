# Deployment

* `docker compose up -d --build` starts `api` (8111) and `web` (3101) bound to localhost,
  with project name `insightforge`, a dedicated network and the `insightforge-data` volume.
  The LLM is the host's Ollama (`host.docker.internal:11434`); no model server is started.
* The API image runs as an unprivileged user and installs bubblewrap. Inside Docker,
  bubblewrap usually cannot create user namespaces, so the sandbox reports `rlimits`.
  For production, run the query worker in its own container with `network_mode: none`, a
  read-only dataset mount and cgroup limits, or grant the runtime user namespaces.
* Configuration is environment-only (`INSIGHTFORGE_*`, see `.env.example`).
* Metadata is SQLite; for multi-instance deployments move it to PostgreSQL (SQLAlchemy +
  Alembic are already in place) and Parquet storage to shared object storage.
