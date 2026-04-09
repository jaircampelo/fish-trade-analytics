{{ config(
    materialized='incremental',
    unique_key=['country_id'],
    schema='gold',
    on_schema_change='append_new_columns',
	indexes=[
		{'columns': ['country_id'], 'unique': True},
	]
) }}

select "country_id"
     , "country_name"
     , current_timestamp as created_at
  from {{ ref('silver_countries') }}

{% if is_incremental() %}
 where "country_id" not in (select "country_id" from {{ this }})
{% endif %}