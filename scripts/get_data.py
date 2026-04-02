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
#                  Getting years interval                   #
#===========================================================#
def get_year_interval(
        interval_scope: int = 0,
        initial_month: str = '01',
) -> dict[str, str]:
    """
    Returns the start and end year-month of the analysis, in the format used by the API (the end year is always the last updated data date).

    Args:
        interval_scope (int): integer corresponding to the year range of the analysis.
        initial_month (str): month number in 'mm' format, corresponding to the start of the analysis.

    Returns:
        dict[str, str]: a dictionary containing the start and end period, in the format {from: yyyy-mm, to: yyyy-mm}.

    Examples:
```python
        get_year_interval(5, '01')
```
    """
    resp = requests.get(f'{BASE_URL}/cities/dates/updated')

    if not resp.ok:
        try:
            error_msg = resp.json().get('error', {}).get('message', resp.text)
        except Exception:
            error_msg = resp.text
        raise requests.HTTPError(f'{resp.status_code}: {error_msg}', response=resp)
    
    max_year = int(resp.json()['data']['year'])
    max_month = resp.json()['data']['monthNumber']
    return {
        'from': f'{max_year - interval_scope}-{initial_month}',
        'to': f'{max_year}-{max_month}'
    }

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
        *,
        flow: Literal['import', 'export'] = 'export',
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
        flow (str): defines which type of data will be returned. If no value is provided, export data is returned.
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
    logging.info(f'Consulting {flow} from {year_interval['from']} → {year_interval['to']}')

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
#                  Read and persist data                    #
#===========================================================#
years_interval = get_year_interval(20)
headings = get_heading_filter()

for flow in ['export', 'import']:
    df = query_comexstat(
        year_interval=years_interval,
        filters=headings,
        metrics=['metricFOB', 'metricKG'],
        details=['country', 'state', 'city', 'heading'],
        flow=flow,
    )

    PROJECT_ROOT = Path(__file__).parent.parent
    output_file = f'fish_trade_{flow}_{years_interval['from'][:4]}{years_interval['from'][5:]}_{years_interval['to'][:4]}{years_interval['to'][5:]}.parquet'
    output_path = PROJECT_ROOT / 'data' / 'raw' / output_file
    output_dir = output_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)

    if not output_path.exists():
        logging.info(f'Persisting data to "{output_file}".')
        df.to_parquet(output_path, index=False, engine='pyarrow')
        logging.info(f'File "{output_file}" sucessfully created. Skipping...')
    else:
        logging.warning(f'File "{output_file}" already exists on {output_dir}.')