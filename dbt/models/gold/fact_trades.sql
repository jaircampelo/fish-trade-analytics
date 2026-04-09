{{ config(
    materialized='incremental',
    unique_key=['trade_date', 'city_id', 'trade_country_id', 'product_category_id', 'trade_flag'],
    schema='gold',
	on_schema_change='append_new_columns',
	indexes=[
		{'columns': ['trade_date', 'city_id', 'trade_country_id', 'product_category_id', 'trade_flag'], 'unique': True},
		{'columns': ['city_id'], 'type': 'btree'},
		{'columns': ['trade_country_id'], 'type': 'btree'},
		{'columns': ['product_category_id'], 'type': 'btree'}
	]
) }}

-- Bring the silver tables from Silver Stage
with imports as (
    select "trade_date"
         , "city_id"
         , "trade_country_id"
         , "product_category_id"
         , "fob_value"
         , "net_weight"
         , "trade_flag"
      from {{ ref('silver_imports') }}

    {% if is_incremental() %}

     where "trade_date" >= (select coalesce(max("trade_date"), '1900-01-01') from {{ this }})

    {% endif %}
),
exports as (
    select "trade_date"
         , "city_id"
         , "trade_country_id"
         , "product_category_id"
         , "fob_value"
         , "net_weight"
         , "trade_flag"
      from {{ ref('silver_exports') }}

    {% if is_incremental() %}

     where "trade_date" >= (select coalesce(max("trade_date"), '1900-01-01') from {{ this }})

    {% endif %}
)

-- union the fact tables
select "trade_date"
     , "city_id"
     , "trade_country_id"
     , "product_category_id"
     , "fob_value"
     , "net_weight"
     , "trade_flag"
     , current_timestamp as "created_at"
  from imports

    union all

select "trade_date"
     , "city_id"
     , "trade_country_id"
     , "product_category_id"
     , "fob_value"
     , "net_weight"
     , "trade_flag"
     , current_timestamp as "created_at"
  from exports