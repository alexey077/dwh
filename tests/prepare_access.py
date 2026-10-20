import os
import sys
from pathlib import Path

import psycopg2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from migrate import create_roles, grant_access

for service in os.environ.get("TEST_SERVICES", "crm,catalog,pos,wms").split(","):
    with psycopg2.connect(os.environ[f"{service.upper()}_TEST_DSN"]) as connection:
        with connection.cursor() as cursor:
            create_roles(cursor)
            grant_access(cursor, service)
print("Access roles prepared with the production grants")
