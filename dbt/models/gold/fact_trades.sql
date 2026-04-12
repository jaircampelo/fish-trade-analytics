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
),

cpi_values as (
    select "cpi_date"
         , "cpi_value"
      from {{ ref('silver_cpi') }}
),

-- union the fact tables
united as (
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
),

-- Get max cpi value
max_cpi as (
    select "cpi_value" as "max_cpi_value"
      from cpi_values
     order by "cpi_date" desc
     limit 1
),

-- Bring CPI value from silver_cpi
joined as (
    select u.*
         , u."fob_value" * (m."max_cpi_value" / c."cpi_value")::decimal(20,2) as "fob_value_real"
      from united           u
      left join cpi_values  c on u."trade_date" = c."cpi_date"
     cross join max_cpi     m
)

-- Final querie
select "trade_date"
     , "city_id"
     , "trade_country_id"
     , "product_category_id"
     , "fob_value"
     , "fob_value_real"
     , "net_weight"
     , "trade_flag"
     , current_timestamp as "created_at"
  from joined