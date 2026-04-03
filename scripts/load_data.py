#===========================================================#
#                       Importing libs                      #
#===========================================================#
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
import os
from pathlib import Path
from dotenv import load_dotenv
import logging

#===========================================================#
#                       Basic configs                       #
#===========================================================#
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path)

#===========================================================#
#                 Connecting to PostgreSQL                  #
#===========================================================#
POSTGRES_USER = os.getenv('POSTGRES_USER')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD')
POSTGRES_DB = os.getenv('POSTGRES_DB')

def get_engine():
    """
    Returns the engine for connection with PostgreSQL.
    """
    logging.info(f'Connecting to localhost:5432/{POSTGRES_DB}')
    return create_engine(
        f'postgresql+psycopg2://{POSTGRES_USER}:{quote_plus(POSTGRES_PASSWORD)}@localhost:5432/{POSTGRES_DB}'
    )

def load_data(engine, file_name: str):
    """
    Load data from file on local path to database on PostgreSQL.

    Args:
        engine: the resulting engine of the function get_engine().
        year_infile_name (str): a file name with the respective extension (e.g. 'aux_cities.parquet').

    Examples:
```python
        load_data('aux_cities.parquet')
```
    """
    if file_name.startswith('aux'):
        table_name = file_name.removeprefix('aux_').removesuffix('.parquet')
        if_exists = 'delete_rows'
    else:
        table_name = '_'.join(file_name.split('_')[:3])
        if_exists = 'append'

    logging.info(f'Start loading data to {table_name} in {POSTGRES_DB} database.')

    files_dir = Path(__file__).resolve().parent.parent / 'data' / 'raw'
    df = pd.read_parquet(files_dir / file_name)
    rows_read = len(df)

    with engine.connect() as conn:
        conn.execute(text('CREATE SCHEMA IF NOT EXISTS bronze;'))
        conn.commit()

    df.to_sql(
        name=table_name,
        con=engine,
        if_exists=if_exists,
        index=False,
        schema='bronze'
    )

    try:
        df_check = pd.read_sql(text(f'''
            SELECT COUNT(1) as total_rows
                FROM bronze.{table_name};
        ''',
        con=engine))

        rows_written = df_check['total_rows'][0]

        logging.info(f'Table={table_name} | rows_read={rows_read} | rows_written={rows_written}')

    except Exception as e:
        logging.error(f'Error validating table {table_name}: {e}\n')

#===========================================================#
#                          Main                             #
#===========================================================#
# List table names
files_dir = Path(__file__).resolve().parent.parent / 'data' / 'raw'
files = os.listdir(files_dir)
logging.info(f'Files to be loaded ({len(files)}): {files}')

# For each file, create a table on database
engine = get_engine()
for file_name in files:
    load_data(engine, file_name)

    