# Airflow requires a separate database for its metadata tables, and this database must be created before Airflow is initialized.

#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE airflow;
EOSQL