{{ config(
    materialized='incremental',
    unique_key=['country_id'],
    schema='silver',
    on_schema_change='append_new_columns',
	indexes=[
		{'columns': ['country_id'], 'unique': True},
	]
) }}

-- Bring the source bronze countries table
with countries_source as (
    select "id"
         , "text"
         , "ingested_at"
         , "loaded_at"
         , row_number() over (
            partition by "id"
            order by "loaded_at" desc
           ) as "row_num"
      from {{ source('bronze', 'countries') }}

    {% if is_incremental() %}
     where loaded_at > (select coalesce(max(loaded_at), '1900-01-01') from {{ this }})
    {% endif %}
),

-- Apply transformations
transformed as (
    select "id"::varchar(10)    as "country_id"
         , "text"::varchar(100) as "country_name"
         , "ingested_at"
         , "loaded_at"
         , "row_num"
      from countries_source
)

select "country_id"
     , "country_name"
     , "ingested_at"
     , "loaded_at"
	 , timestamp as "processed_at"
  from transformed
 where "row_num" = 1