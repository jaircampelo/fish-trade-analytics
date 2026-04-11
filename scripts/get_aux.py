#===========================================================#
#                       Importing libs                      #
#===========================================================#
import requests
import pandas as pd
from typing import Literal
from pathlib import Path
import logging

#===========================================================#
#                       Basic configs                       #
#===========================================================#
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
# Base URL from comexstat API
BASE_URL = 'https://api-comexstat.mdic.gov.br'

#===========================================================#
#         Create function to extract auxiliare data         #
#===========================================================#
def get_aux(
        base_url: str,
        aux_table: Literal['uf', 'cities', 'countries']
) -> pd.DataFrame:
    """
    Returns a DataFrame from an auxiliary table endpoint.

    Args:
        base_url (str): base URL of the ComexStat API.
        aux_table (str): auxiliary table to query. Accepted values: 'uf', 'cities', 'countries'.

    Returns:
        pd.DataFrame: a DataFrame containing the codes and descriptions of the requested auxiliary table.

    Examples:
```python
        get_aux('https://api-comexstat.mdic.gov.br', 'countries')
```
    """
    url = f"{base_url}/tables/{aux_table}"
    logging.info(f'Fetching auxiliary table "{aux_table}" from {url}.')

    resp = requests.get(url)

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

    logging.info(f'Table "{aux_table}" fetched successfully. Rows: {len(df_records)}.')

    return df_records

#===========================================================#
#               Extract and persist aux data                #
#===========================================================#
def run_get_aux():

    for aux in ['uf', 'cities', 'countries']:
        logging.info(f'Starting extraction of auxiliary table "{aux}".')

        df = get_aux(BASE_URL, aux)

        df['ingested_at'] = pd.Timestamp.now()

        PROJECT_ROOT = Path(__file__).parent.parent
        output_file = f'aux_{aux}.parquet'
        output_path = PROJECT_ROOT / 'data' / 'raw' / output_file
        output_dir = output_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)

        logging.info(f'Persisting "{aux}" to "{output_file}".')
        df.to_parquet(output_path, index=False, engine='pyarrow')
        logging.info(f'File "{output_file}" successfully created.')
        
    logging.info('Auxiliary tables extraction completed.')