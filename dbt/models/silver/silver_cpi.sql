{{ config(
    materialized='incremental',
    unique_key=['cpi_date'],
    schema='silver',
    on_schema_change='append_new_columns',
	indexes=[
		{'columns': ['cpi_date'], 'unique': True},
	]
) }}

-- Bring the source bronze cpi table
with cpi_source as (
    select "year"
         , "period"
         , "value"
         , "ingested_at"
         , "loaded_at"
         , row_number() over (
            partition by "year", "period"
            order by "loaded_at" desc
           ) as "row_num"
      from {{ source('bronze', 'cpi') }}
     where "period" != 'M13'

    {% if is_incremental() %}
       and loaded_at > (select coalesce(max(loaded_at), '1900-01-01') from {{ this }})
    {% endif %}
),

-- Apply transformations
transformed as (
    select 
           -- Date column with null treatment
           to_date(
                concat(
                    coalesce("year", '1990'), '/'
                  , coalesce(lpad(regexp_replace("period", '[^0-9]', '', 'g'), 2, '0'), '01'), '/'
                  , 1
                )
              , 'YYYY/MM/DD'
           )                        as "cpi_date"

           -- Apply null treatments
         , case 
              when "value" = '-' then '0'
              else coalesce("value", '0')
           end                      as "cpi_value"

         , "ingested_at"
         , "loaded_at"
         , "row_num"
      from cpi_source
),

-- Defined types
final as (
    select "cpi_date"::date
         , "cpi_value"::decimal(20,2)
         , case when "cpi_value"::decimal(20,2) > 0 then true else false end as "is_valid_cpi_value"
         , "ingested_at"::timestamp
         , "loaded_at"::timestamp
         , "row_num"::integer
      from transformed
)

-- Final querie with cleaned data
select "cpi_date"
     , "cpi_value"
     , "ingested_at"
     , "loaded_at"
     , current_timestamp as "processed_at"
  from final
 where "row_num"            = 1
   and "is_valid_cpi_value" = true