# Production deployment guide (backend)

This guide focuses on the backend FastAPI service for a two-server SaaS setup.

Quick start (production)
- Copy env and install
  cp .env.example .env
  python3 -m venv venv && source venv/bin/activate
  pip install --upgrade pip && pip install -r requirements.txt
- Migrate master DB (reads ALEMBIC_DB_URL or DATABASE_URL)
  ALEMBIC_DB_URL=postgresql+psycopg2://<user>:<pass>@<host>:5432/<master_db> \
  alembic -c alembic.ini upgrade head
- Run the API
  gunicorn -k uvicorn.workers.UvicornWorker -w 4 -b 0.0.0.0:8000 app.main:app

Nginx reverse proxy (preserve tenant headers)
  server {
    listen 443 ssl;
    server_name api.yourdomain.com;

    location / {
      proxy_pass http://127.0.0.1:8000;
      proxy_set_header Host $host;
      proxy_set_header X-Real-IP $remote_addr;
      proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
      proxy_set_header X-Forwarded-Proto $scheme;
      proxy_set_header X-Tenant-Type $http_x_tenant_type;
      proxy_set_header X-Tenant-Slug $http_x_tenant_slug;
      proxy_set_header X-Tenant-Id $http_x_tenant_id;
    }
  }

Multi-tenant operations
- Create tenant DB for existing organization id:
  ./scripts/create_tenant_db.sh <ORG_ID>
- Create org and tenant DB (with sample data):
  python create_tenant_with_db.py
- Sync all tenants via API (requires admin token):
  API_BASE_URL=https://api.yourdomain.com \
  ADMIN_TOKEN={{ADMIN_BEARER_TOKEN}} \
  ./scripts/sync_all_tenants.sh

Environment variables (see .env.example)
- DATABASE_URL: async URL for master DB (postgresql+asyncpg://...)
- ALEMBIC_DB_URL: sync URL for Alembic CLI (postgresql+psycopg2://...)
- SECRET_KEY, CORS_ORIGINS, STRIPE_* and SMTP_* as needed.
