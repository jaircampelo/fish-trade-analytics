import logging
import subprocess
from datetime import datetime, timedelta
from airflow.decorators import dag, task
import sys

sys.path.insert(0, '/opt/airflow/scripts')

from get_data import run_get_data
from get_aux import run_get_aux
from load_data import run_load_data

# Set default args
default_args = {
    'owner': 'jaircampelo',
    'depends_on_past': False,
    'start_date': datetime(2026, 4, 10),
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'execution_timeout': timedelta(hours=1)
}

# Follows DRY (Don't Repeat Yourself) principle, reducing repetition.
def run_dbt_command(command, select):
    base_path = '/opt/airflow/dbt'
    args = [
        'dbt', command,
        '--select', select,
        '--profiles-dir', base_path,
        '--project-dir', base_path
    ]
    result = subprocess.run(args, cwd=base_path, capture_output=True, text=True)

    logging.info(result.stdout)
    
    if result.returncode != 0:
        raise Exception(f"dbt {command} failure for {select}: {result.stderr}")
    return result.stdout

@dag(
    dag_id='fish_trade_pipeline',
    default_args=default_args,
    description='Data pipeline from extraction to serving fish trade data from COMEX STAT API.',
    schedule='0 10 1 * *',
    catchup=False,
    tags=['fish', 'trade', 'elt']
)
def fish_trade_pipeline():

    # Extract main data from fish trade imports and exports using COMEX STAT API.
    @task
    def extract_main():
        run_get_data()

    # Extract aux data from COMEX STAT API.
    @task
    def extract_aux():
        run_get_aux()

    # Load data extracted to PostgreSQL.
    @task
    def load():
        run_load_data()

    # Apply DBT transformations on the tables loaded to PostgreSQL.
    @task
    def transform():
        return run_dbt_command('run', 'silver')
    
    # Execute DBT tests in Silver layer.
    @task
    def test_transform():
        return run_dbt_command('test', 'silver')
    
    # Prepare the data for use in visualization tool.
    @task
    def aggregate():
        return run_dbt_command('run', 'gold')
    
    # Execute DBT tests in Gold layer.
    @task
    def test_aggregate():
        return run_dbt_command('test', 'gold')
    
    # Generate DBT docs
    @task
    def generate_docs():
        base_path = '/opt/airflow/dbt'
        args = [
            'dbt', 'docs', 'generate',
            '--profiles-dir', base_path,
            '--project-dir', base_path
        ]
        result = subprocess.run(args, cwd=base_path, capture_output=True, text=True)
        logging.info(result.stdout)
        if result.returncode != 0:
            raise Exception(f"dbt docs generate failure: {result.stderr}")
        return result.stdout
    
    [extract_main(), extract_aux()] >> load() >> transform() >> test_transform() >> aggregate() >> test_aggregate() >> generate_docs()

fish_trade_pipeline()