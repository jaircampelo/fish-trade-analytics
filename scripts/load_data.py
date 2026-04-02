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
    logging.info(f'Connecting to localhost:5432/{POSTGRES_DB}')
    return create_engine(
        f'postgresql+psycopg2://{POSTGRES_USER}:{quote_plus(POSTGRES_PASSWORD)}@localhost:5432/{POSTGRES_DB}'
    )

engine = get_engine()

def load_data(table_name: str, df: pd.DataFrame):
    rows_read = len(df)

    logging.info(f'Start loading data to {table_name} in {POSTGRES_DB} database.')

    df = df.to_sql(
        name=table_name,
        con=engine,
        if_exists='append',
        index=False,
    )

    try:
        df_check = pd.read_sql(f'''
            SELECT COUNT(1) as total_rows
                FROM {table_name};
        ''', con=engine)

        rows_written = df_check['total_rows'][0]

        logging.info(f'Table={table_name} | rows_read={rows_read} | rows_written={rows_written}')

    except Exception as e:
        logging.error(f'Error validating table {table_name}: {e}')

load_data('test', pd.read_parquet('data/raw/fish_trade_export_200601_202602.parquet'))

    