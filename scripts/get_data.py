#===========================================================#
#                       Importing libs                      #
#===========================================================#
import requests
import pandas as pd
from typing import Literal
from pathlib import Path
from datetime import date
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from time import sleep
import logging
import os

#===========================================================#
#                       Basic configs                       #
#===========================================================#
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_URL = 'https://api-comexstat.mdic.gov.br'

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path, override=False)

#===========================================================#
#                     Database connection                   #
#===========================================================#
def get_engine():
    """
    Returns the engine for connection with PostgreSQL.
    """
    user = os.getenv('POSTGRES_USER')
    password = os.getenv('POSTGRES_PASSWORD')
    database = os.getenv('POSTGRES_DB')
    host = os.getenv('POSTGRES_HOST') or 'localhost'
    port = os.getenv('POSTGRES_PORT', '5432')

    logging.info(f'Connecting to {host}:{port}/{database}.')
    return create_engine(f'postgresql+psycopg2://{user}:{quote_plus(password)}@{host}:{port}/{database}')

#===========================================================#
#                 Create landing metatable                  #
#===========================================================#
def create_landing_metatable(engine):
    """
    Create a landing metatable (if not exists) for monitoring the data ingestion.

    Args:
        engine: the resulting engine of the function get_engine().
    """
    with engine.begin() as conn:
        conn.execute(text('CREATE SCHEMA IF NOT EXISTS metadata;'))
        conn.execute(text(f"""
            CREATE TABLE IF NOT EXISTS metadata.landing_meta_table (
                  id                    INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY
                , heading_code          VARCHAR(4)      NOT NULL
                , flow                  VARCHAR(20)     NOT NULL
                , date_from             DATE            NOT NULL
                , date_to               DATE            NOT NULL
                , relative_file_path    VARCHAR(500)    NOT NULL
                , ingested_at           TIMESTAMP       NOT NULL DEFAULT NOW()
            );
        """))
        logging.info('Landing metatable created/verified successfully.')

#===========================================================#
#              Getting fish related SH4 codes               #
#===========================================================#
def get_heading_filter() -> list[dict[str, list]]:
    """
    Returns the SH4 codes related to fishery resources, from 0301 to 0308.

    Examples:
```python
        get_heading_filter()
```
    """
    resp = requests.get(f'{BASE_URL}/cities/filters/heading', params={'language': 'pt'})

    if not resp.ok:
        try:
            error_msg = resp.json().get('error', {}).get('message', resp.text)
        except Exception:
            error_msg = resp.text
        raise requests.HTTPError(f'{resp.status_code}: {error_msg}', response=resp)

    headings = resp.json()['data'][0]

    filtered = [
        heading['id']
        for heading in headings
        if heading['id'].startswith('03') and not heading['id'].endswith('09')
    ]

    return [
        {
            'filter': 'heading',
            'values': filtered
        }
    ]

#===========================================================#
#     Request function tha returns a json or dataframe      #
#===========================================================#
def query_comexstat(
        year_interval: dict[str, str],
        filters: list[dict[str, list]],
        metrics: list[str],
        details: list[str],
        flow: Literal['import', 'export'],
        *,
        month_detail: bool = True,
        df: bool = True,
) -> pd.DataFrame:
    """
    Returns a DataFrame from the API request.

    Args:
        year_interval (tuple[str, str]): a tuple with the year range of the request.
        filters (dict[str, list]): a dictionary with the filter type and its values in a list.
        metrics (list[str]): defines the metrics to be evaluated.
        details (list[str]): defines the categories by which the metrics will be broken down (determines the granularity of the request).
        flow (str): defines which type of data will be returned.
        month_detail (bool): defines the time granularity. If no value is provided, monthly granularity is used.
        df (bool = True): If no value is provided, it returns a dataframe.

    Returns:
        (pd.DataFrame): a DataFrame with the required metrics for the given period, considering the categories defined in the detail breakdown.

    Examples:
```python
        query_comexstat(
            ('2025-01', '2025-12'),
            {heading: ['0301', '0302', '0303']},
            ['metricFOB', 'metricKG'],
            ['state', 'heading'],
            flow='import',
            month_detail=True,
            df=True
        )
```
    """
    heading_values = [filter['values'] for filter in filters]

    logging.info(f'Headings found: {heading_values}')
    logging.info(f'Consulting {flow} from {year_interval["from"]} → {year_interval["to"]}')

    payload = {
        'flow': flow,
        'monthDetail': month_detail,
        'period': year_interval,
        'filters': filters,
        'details': details,
        'metrics': metrics,
    }
 
    resp = requests.post(
        f'{BASE_URL}/cities',
        json=payload,
        params={'language': 'pt'},
    )

    if not resp.ok:
        try:
            error_msg = resp.json().get('error', {}).get('message', resp.text)
        except Exception:
            error_msg = resp.text
        raise requests.HTTPError(f'{resp.status_code}: {error_msg}', response=resp)
    
    body = resp.json()
    data = body.get('data', {})
    records = data.get('list', data) if isinstance(data, dict) else data
    df_records = pd.DataFrame(records)
    
    rows = len(records)
    logging.info(f'Rows read: {rows}')

    if df == True:
        result = df_records
    else:
        result = records

    return result

#===========================================================#
#              Get latest available date from API           #
#===========================================================#
def get_latest_api_last_date() -> date:
    """
    Returns the date from the last updated Comexstat API data.
    """
    resp = requests.get(f'{BASE_URL}/cities/dates/updated')

    if not resp.ok:
        try:
            error_msg = resp.json().get('error', {}).get('message', resp.text)
        except Exception:
            error_msg = resp.text
        raise requests.HTTPError(f'{resp.status_code}: {error_msg}', response=resp)
    
    data = resp.json()['data']

    return date(int(data['year']), int(data['monthNumber']), 1)

#===========================================================#
#      Get latest ingested date from landing metatable      #
#===========================================================#
def get_latest_meta_last_date(
        engine,
        flow: Literal['import', 'export']
    ) -> date | None:
    """
    Returns the last date from landing_meta_table

    Args:
        engine: the resulting engine of the function get_engine().
        flow (str): defines which flow the last date is from.

    Returns:
        (date): a date from the given flow on landing_meta_table.

    Examples:
```python
        get_latest_meta_last_date(
            engine=get_engine(),
            flow='import',
        )
```
    """
    query = text(f"""
        SELECT MAX(date_to)
          FROM metadata.landing_meta_table
         WHERE flow = :flow
    """)

    with engine.connect() as conn:
        result = conn.execute(query, {'flow': flow})
        row = result.fetchone()
        return row[0] if row and row[0] else None
    
#===========================================================#
#           Insert record into landing metatable            #
#===========================================================#
def insert_landing_meta_record(engine, heading_code: str, flow: Literal['import', 'export'], date_from: date, date_to: date, relative_file_path: str):
    """
    Insert metadata from the API request.

    Args:
        engine: the resulting engine of the function get_engine().
        heading_code (str): SH4 code extracted from API request.
        flow (str): flow (import, export) extracted from API request.
        date_from (date): initial date from the data extracted.
        date_to (date): final date from the data extracted.
        relative_file_path (str): relative path where the data extracted persist.

    Examples:
```python
        insert_landing_meta_record(
            engine=get_engine(),
            flow='import',
            date_from=date(2006-1-1),
            date_to=date(2020-31-1),
            relative_file_path='project_name/data/raw/file.parquet'
        )
```
    """
    query = text(f"""
        INSERT INTO metadata.landing_meta_table
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
#                  Incremental ingestion                    #
#===========================================================#
def run_incremental_ingestion(
        engine,
        heading_codes: list[dict],
        flows: list[str],
        start_year: int,
        *,
        final_year: int | None = None,
    ):
    """
    Run the incremental Comexstat API ingestion from the given metrics.
    \nIf metatable is filled with data, the final year is always the year from the last updated data.

    Args:
        engine: the resulting engine of the function get_engine().
        heading_codes (list[dict]): SH4 codes for API request.
        flows (list[str]): list of available flows (import, export) for API request.
        start_year (int): initial year for data extraction.
        final_year (int): final year for data extraction.

    Examples:
```python
        run_incremental_ingestion(
            engine=get_engine(),
            heading_codes=[
                {
                    'filter': 'heading',
                    'values': ['0301', '0302', ..., '0308']
                }
            ]
            flows=['import', 'export'],
            start_year=2006,
            final_year=2020,
        )
```
    """
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    api_last_date = get_latest_api_last_date()
    logging.info(f'Latest available date from API: {api_last_date}.')

    for flow in flows:
        logging.info(f'Checking Flow {flow}.')
        meta_last_date = get_latest_meta_last_date(engine, flow)

        # First ingestion — no landing metatable record
        if meta_last_date is None:
            date_from = date(start_year, 1, 1)

            if final_year is None or final_year == api_last_date.year:
                date_to = api_last_date
                logging.info(f'No previous ingestion found. Starting from {date_from} to {date_to}.')
            elif final_year > api_last_date.year:
                date_to = api_last_date
                logging.info(f'No data available for {final_year}, running extraction until {api_last_date}.')
            else:
                date_to = date(final_year, 12, 1)
                logging.info(f'No previous ingestion found. Starting from {date_from} to {date_to}.')

        elif api_last_date > meta_last_date:
            # Skip one month from date_to
            if meta_last_date.month == 12:
                date_from = date(meta_last_date.year + 1, 1, 1)
                date_to = api_last_date
            else:
                date_from = date(meta_last_date.year, meta_last_date.month + 1, 1)
                date_to = api_last_date
            logging.info(f'New data available. Ingesting from {date_from} to {date_to}.')

        else:
            logging.info(f'Flow {flow} is up to date. Skipping...')
            continue

        year_interval = {
            'from': date_from.strftime('%Y-%m'),
            'to': date_to.strftime('%Y-%m'),
        }

        df = query_comexstat(
            year_interval=year_interval,
            filters=heading_codes,
            metrics=['metricFOB', 'metricKG'],
            details=['country', 'state', 'city', 'heading'],
            flow=flow,
        )

        df['ingested_at'] = pd.Timestamp.now()

        output_file = f'fish_trade_{flow}_{date_from.strftime("%Y%m")}_{date_to.strftime("%Y%m")}.parquet'
        output_path = PROJECT_ROOT / 'data' / 'raw' / output_file
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logging.info(f'Persisting data to "{output_file}".')
        df.to_parquet(output_path, index=False, engine='pyarrow')
        logging.info(f'File "{output_file}" successfully created.')

        relative_file_path = str(Path('data') / 'raw' / output_file)
        for heading_code in heading_codes[0]['values']:
            insert_landing_meta_record(engine, heading_code, flow, date_from, date_to, relative_file_path)

        logging.info(f'Landing metatable updated for flow {flow}.')

        sleep(5)

#===========================================================#
#                          Main                             #
#===========================================================#
def run_get_data():
    
    engine = get_engine()
    create_landing_metatable(engine)

    heading_codes = get_heading_filter()
    flows = ['export', 'import']

    run_incremental_ingestion(engine, heading_codes, flows, start_year=2006)