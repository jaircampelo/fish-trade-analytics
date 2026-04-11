#===========================================================#
#                       Importing libs                      #
#===========================================================#
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from time import sleep
import logging
import os

#===========================================================#
#                       Basic configs                       #
#===========================================================#
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

BASE_URL = 'https://api.bls.gov/publicAPI/v2/timeseries/data/'
SERIES_ID = ['CUUR0000SA0']

env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(env_path, override=False)

BLS_API_KEY = os.getenv('BLS_API_KEY')

#===========================================================#
#            Create function to extract CPI data            #
#===========================================================#
def extract_cpi_data(
    series_id: list,
    start_year: int,
    end_year: int,
    api_key: str,
    df: bool = True,
) -> pd.DataFrame:
    """
    Returns a DataFrame from the API request.

    Args:
        series_id (str): identifier code from temporal series in Bureau of Labor Statistics.
        start_year (int): start year of data.
        end_year (int): end year of data.
        api_key (str): API KEY requested at [https://data.bls.gov/registrationEngine/](https://data.bls.gov/registrationEngine/).
        df (bool = True): If no value is provided, it returns a dataframe.

    Returns:
        (pd.DataFrame): a DataFrame with the required metrics for the given period.

    Examples:
```python
        extract_cpi_data(
            'CUUR0000SA0',
            2006,
            2016,
            API_KEY,
            df=True,
        )
```
    """

    logging.info(f'Consulting CPI values from {start_year} → {end_year}')

    payload = {
        'seriesid': series_id,
        'startyear': start_year,
        'endyear': end_year,
        'registrationkey': api_key,
    }

    resp = requests.post(
        BASE_URL,
        json=payload
    )

    if not resp.ok:
        try:
            error_msg = resp.json().get('message', [resp.text])[0]
        except Exception:
            error_msg = resp.text
        raise requests.HTTPError(f'{resp.status_code}: {error_msg}', response=resp)

    body = resp.json()

    if body.get('status') != 'REQUEST_SUCCEEDED':
        logging.error(f'{body["status"]}: {body["message"]}')
        return pd.DataFrame() if df else []
    
    try:
        series_list = body.get('Results', {}).get('series', [])
        records = series_list[0].get('data', []) if series_list else []
    except (IndexError, KeyError):
        records = []

    logging.info(f'Rows read: {len(records)}')

    if not df:
        return records
    
    # Processing DataFrame
    df_records = pd.DataFrame(records)

    if df:
        return df_records
    
#===========================================================#
#                    Get years interval                     #
#===========================================================#
def split_year_interval(start_year: int, end_year:int) -> list[tuple[int, int]]:
    """
    Splits a date interval into chunks of 10 years if the interval exceeds 10 years.
    """
    if end_year - start_year <= 10:
        return [(start_year, end_year)]
    
    intervals = []
    current_start = start_year

    while current_start < end_year:
        current_end = min(current_start + 10, end_year)
        intervals.append((current_start, current_end))
        current_start = current_end + 1

    return intervals
#===========================================================#
#               Extract and persist CPI data                #
#===========================================================#
def run_get_cpi():

    logging.info(f'Starting extraction of auxiliary table cpi.')

    intervals = split_year_interval(2006, pd.Timestamp.now().year)
    
    dfs = []
    for start_year, end_year in intervals:


        df_chunk = extract_cpi_data(
            series_id=SERIES_ID,
            start_year=start_year,
            end_year=end_year,
            api_key=BLS_API_KEY,
        )

        df_chunk = df_chunk.astype(str)
        df_chunk['ingested_at'] = pd.Timestamp.now()
        dfs.append(df_chunk)
        sleep(5)

    df = pd.concat(dfs, ignore_index=True)

    PROJECT_ROOT = Path(__file__).parent.parent
    output_file = f'aux_cpi.parquet'
    output_path = PROJECT_ROOT / 'data' / 'raw' / output_file
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    logging.info(f'Persisting cpi data to "{output_file}".')
    df.to_parquet(output_path, index=False, engine='pyarrow')
    logging.info(f'File "{output_file}" successfully created.')

    logging.info('Auxiliary table extraction completed.')