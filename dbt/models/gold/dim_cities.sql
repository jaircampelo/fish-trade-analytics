{{ config(
    materialized='incremental',
    unique_key=['city_id'],
    schema='gold',
    on_schema_change='append_new_columns',
	indexes=[
		{'columns': ['city_id'], 'unique': True},
	]
) }}

select "city_id"
     , "city_name"
     , "state_name"
     , "city_uf"
     , current_timestamp as created_at
  from {{ ref('silver_cities') }}

{% if is_incremental() %}
 where "city_id" not in (select "city_id" from {{ this }})
{% endif %}