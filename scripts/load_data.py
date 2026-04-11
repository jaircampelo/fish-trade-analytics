#===========================================================#
#                       Importing libs                      #
#===========================================================#
import pandas as pd
from sqlalchemy import create_engine, text
from urllib.parse import quote_plus
from pathlib import Path
from dotenv import load_dotenv
from typing import Literal
from datetime import date
import os
import logging

#===========================================================#
#                       Basic configs                       #
#===========================================================#
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path, override=False)

#===========================================================#
#                 Connecting to PostgreSQL                  #
#===========================================================#
user = os.getenv('POSTGRES_USER')
password = os.getenv('POSTGRES_PASSWORD')
database = os.getenv('POSTGRES_DB')
host = os.getenv('POSTGRES_HOST') or 'localhost'
port = os.getenv('POSTGRES_PORT', '5432')

def get_engine():
    """
    Returns the engine for connection with PostgreSQL.
    """
    logging.info(f'Connecting to localhost:5432/{database}')
    return create_engine(
        f'postgresql+psycopg2://{user}:{quote_plus(password)}@{host}:{port}/{database}'
    )

#===========================================================#
#                  Create bronze metatable                  #
#===========================================================#
def create_bronze_metatable(engine):
    """
    Create a bronze metatable (if not exists) for monitoring the data processing.

    Args:
        engine: the resulting engine of the function get_engine().
    """
    with engine.begin() as conn:
        conn.execute(text('CREATE SCHEMA IF NOT EXISTS metadata;'))
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS metadata.bronze_meta_table (
                  id            INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
                , heading_code  VARCHAR(4)      NOT NULL
                , flow          VARCHAR(20)     NOT NULL
                , date_from     DATE            NOT NULL
                , date_to       DATE            NOT NULL
                , relative_file_path     VARCHAR(500)    NOT NULL
                , processed_at   TIMESTAMP       NOT NULL DEFAULT NOW()
            );
        """))
        logging.info('Bronze metatable created/verified successfully.')

#===========================================================#
#    Get latest ingested date_from from landing metatable   #
#===========================================================#
def get_latest_landing_meta_date_from(
        engine,
        flow: Literal['import', 'export']
    ) -> date | None:
    """
    Returns the last date_from from landing_meta_table

    Args:
        engine: the resulting engine of the function get_engine().
        flow (str): defines which flow the last date_from is from.

    Returns:
        (date): a date from the given flow on landing_meta_table.

    Examples:
```python
        get_latest_landing_meta_date_from(
            engine=get_engine(),
            flow='import',
        )
```
    """
    query = text(f"""
        SELECT MAX(date_from)
          FROM metadata.landing_meta_table
         WHERE flow = :flow
    """)

    with engine.begin() as conn:
        result = conn.execute(query, {'flow': flow})
        row = result.fetchone()
        return row[0] if row and row[0] else None
    
#===========================================================#
#     Get latest processed date_to from bronze metatable    #
#===========================================================#
def get_latest_bronze_meta_date_to(
        engine,
        flow: Literal['import', 'export']
    ) -> date | None:
    """
    Returns the last date_to from bronze_meta_table

    Args:
        engine: the resulting engine of the function get_engine().
        flow (str): defines which flow the last date_to is from.

    Returns:
        (date): a date from the given flow on bronze_meta_table.

    Examples:
```python
        get_latest_bronze_meta_date_to(
            engine=get_engine(),
            flow='import',
        )
```
    """
    query = text(f"""
        SELECT MAX(date_to)
          FROM metadata.bronze_meta_table
         WHERE flow = :flow
    """)

    with engine.begin() as conn:
        result = conn.execute(query, {'flow': flow})
        row = result.fetchone()
        return row[0] if row and row[0] else None
    
#===========================================================#
#          Insert record into bronze metatable              #
#===========================================================#
def insert_bronze_meta_record(
        engine,
        heading_code: str,
        flow: Literal['import', 'export'],
        date_from: date, 
        date_to: date,
        relative_file_path: str
    ):
    """
    Insert metadata from the landing processed files.

    Args:
        engine: the resulting engine of the function get_engine().
        heading_code (str): SH4 code processed from landing_meta_table.
        flow (str): flow (import, export) processed from landing_meta_table.
        date_from (date): initial date from the data processed.
        date_to (date): final date from the data processed.
        relative_file_path (str): relative path where the data extracted persist.

    Examples:
```python
        insert_bronze_meta_record(
            engine=get_engine(),
            flow='import',
            date_from=date(2006-1-1),
            date_to=date(2020-31-1),
            relativefile_path='project_name/data/raw/file.parquet'
        )
```
    """
    query = text(f"""
        INSERT INTO metadata.bronze_meta_table
            (heading_code, flow, date_from, date_to, relative_file_path)
        VALUES
            (:heading_code, :flow, :date_from, :date_to, :relative_file_path)
    """)

    with engine.begin() as conn:
        conn.execute(
            query,
            {
                'heading_code': heading_code,
                'flow': flow,
                'date_from': date_from,
                'date_to': date_to,
                'relative_file_path': relative_file_path,
            }
        )

#===========================================================#
#                    Incremental loading                    #
#===========================================================#
def run_incremental_loading(
        engine,
        file_name: str,
        schema: str,
    ):
    """
    Run the incremental loading process from the given files to PostgreSQL.

    Args:
        engine: the resulting engine of the function get_engine().
        file_name (str): a file name with the respective extension (e.g. 'aux_cities.parquet').
        schema (str): define the schema where the table is.

    Examples:
```python
        run_incremental_loading(
            engine=get_engine(),
            file_name='aux_cities.parquet',
            schema='bronze',
        )
```
    """
    if file_name.startswith('aux'):
        table_name = file_name.removeprefix('aux_').removesuffix('.parquet')
    else:
        table_name = '_'.join(file_name.split('_')[:3])

        file_name_list = file_name.split('_')

        file_strdate_from = file_name_list[3]
        file_year_from = file_strdate_from[:4]
        file_month_from = file_strdate_from[4:]
        file_date_from = date(int(file_year_from), int(file_month_from), 1)

        file_strdate_to = file_name_list[4]
        file_year_to = file_strdate_to[:4]
        file_month_to = file_strdate_to[4:6]
        file_date_to = date(int(file_year_to), int(file_month_to), 1)

    files_dir = Path(__file__).resolve().parent.parent / 'data' / 'raw'
    df = pd.read_parquet(files_dir / file_name)
    
    df['loaded_at'] = pd.Timestamp.now()

    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS {schema};'))

    if file_name.startswith('aux'):
        with engine.begin() as conn:
            # Use try/except in case table does not exist on first exec
            try:
                conn.execute(text(f'TRUNCATE TABLE {schema}.{table_name};'))
            except Exception:
                pass

        df.to_sql(
            name=table_name,
            con=engine,
            if_exists='append',
            index=False,
            schema=schema,
        ) 
    else:
        flow = file_name_list[2] # fish_trade_export - índice 2
        logging.info(f'Checking flow {flow}.')

        landing_last_date_from = get_latest_landing_meta_date_from(engine, flow)
        bronze_last_date_to = get_latest_bronze_meta_date_to(engine, flow)

        if bronze_last_date_to is None:
            df.to_sql(
                name=table_name,
                con=engine,
                if_exists='append',
                index=False,
                schema=schema,
            )
            logging.info(f'No previous loading found. Starting load data from {file_name} to {table_name} in {database} database.')

        elif landing_last_date_from <= bronze_last_date_to:
            logging.info(f'Flow {flow} is up to date. Skipping...')
            return
        
        else:
            if landing_last_date_from.strftime('%Y%m') == file_name_list[3]:
                df.to_sql(
                    name=table_name,
                    con=engine,
                    if_exists='append',
                    index=False,
                    schema=schema,
                )
                logging.info(f'New data available. loading data from {file_name} to {table_name} in {database} database.')
            else:
                logging.info(f'File {file_name} is already loaded.')
                return
                

        query = text(f"""
            SELECT distinct heading_code
                FROM metadata.landing_meta_table
                WHERE flow = :flow
        """)

        with engine.begin() as conn:
            result = conn.execute(query, {'flow': flow})
            rows = result.fetchall()

            headings = [row[0] for row in rows]

        if not file_name.startswith('aux'):
            relative_file_path = str(Path('data') / 'raw' / file_name)
            for heading in headings:
                insert_bronze_meta_record(engine, heading, flow, file_date_from, file_date_to, relative_file_path)

            logging.info(f'Bronze metatable updated for flow {flow}.')

#===========================================================#
#                          Main                             #
#===========================================================#
def run_load_data():

    # List table names
    files_dir = Path(__file__).resolve().parent.parent / 'data' / 'raw'
    files = os.listdir(files_dir)
    logging.info(f'Files available to probably be loaded ({len(files)}): {files}')
    engine = get_engine()

    # Create (if not exists) bronze_meta_table
    create_bronze_metatable(engine)

    # For each file, create a table on database
    schema = 'bronze'
    for file_name in files:
        run_incremental_loading(engine, file_name, schema)