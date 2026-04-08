{{ config(
    materialized='incremental',
    unique_key=['city_id'],
    schema='silver',
    on_schema_change='append_new_columns',
	indexes=[
		{'columns': ['city_id'], 'unique': True},
	]
) }}

-- Bring the source bronze cities table
with cities_source as (
    select "id"
         , "text"
         , substring("text" from position(' - ' in "text") + 3) as "uf"
         , "noMunMin"
         , "ingested_at"
         , "loaded_at"
         , row_number() over (
            partition by "id"
            order by "loaded_at" desc
           ) as "row_num"
      from {{ source('bronze', 'cities') }}

    {% if is_incremental() %}
     where loaded_at > (select coalesce(max(loaded_at), '1900-01-01') from {{ this }})
    {% endif %}
),
states_source as (
    select "text"
         , "id"
         , "uf"
      from {{ source('bronze', 'uf') }}
),

-- Join cities with states
joined as (
    select c.*
         , s."text" as "state_name"
      from cities_source c
      left
      join states_source s on c."uf" = s."uf"
),

-- Apply transformations
transformed as (
    select "id"::char(7)                as "city_id"
         , "noMunMin"::varchar(100)     as "city_name"
         , "text"::varchar(100)         as "city_uf"
         , "state_name"::varchar(50)    as "state_name"
         , "ingested_at"
         , "loaded_at"
         , "row_num"
      from joined
)

select "city_id"
     , "city_name"
     , "state_name"
     , "city_uf"
     , "ingested_at"
     , "loaded_at"
	 , timestamp as "processed_at"
  from transformed
 where "row_num" = 1