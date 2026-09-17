# Architecture contract

Python 3.12 FastAPI and React/Vite. Evidence → deterministic decoding → deterministic risk signals/scoring → NOOA interpretation → report.

Frozen typed evidence retains source IDs throughout. Agents cannot overwrite facts. Claims need validated evidence references. Completeness is separate from risk; missing information never implies safety.

Storage will use repository interfaces, SQLAlchemy SQLite/PostgreSQL adapters and Alembic migrations. Analysis logic does not depend on database sessions.

Cloudflare hosts the frontend. Docker is the baseline API deployment. A separate Workers experiment must verify execution and dependencies before proposing an alternative.