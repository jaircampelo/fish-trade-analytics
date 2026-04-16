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
         , trim(split_part("text", '-', 2) as "uf"
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
regions as (
    select uf
         , region
      from {{ ref('seed_state_regions') }}
),

-- Join cities with states
joined as (
    select c."id"
         , c."text"
         , c."uf"
         , c."noMunMin"
         , c."ingested_at"
         , c."loaded_at"
         , c."row_num"
         , s."text" as "state_name"
         , case when r."region" is null then "Não se aplica" else r."region" end as "region"
      from cities_source        c
      left join states_source   s on c."uf" = s."uf"
      left join regions         r on c."uf" = r."uf"
),

-- Apply transformations
transformed as (
    select "id"::char(7)                as "city_id"
         , "noMunMin"::varchar(100)     as "city_name"
         , "text"::varchar(100)         as "city_uf"
         , "state_name"::varchar(50)    as "state_name"
         , "uf"::char(2)                as "uf"
         , "region"::varchar(50)        as "region"
         , "ingested_at"
         , "loaded_at"
         , "row_num"
      from joined
)

select "city_id"
     , "city_name"
     , "state_name"
     , "uf"
     , "city_uf"
     , "region"
     , "ingested_at"
     , "loaded_at"
	 , current_timestamp as "processed_at"
  from transformed
 where "row_num" = 1