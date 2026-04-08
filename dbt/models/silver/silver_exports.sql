{{ config(
    materialized='incremental',
    unique_key=['trade_date', 'city_id', 'trade_country_id', 'product_category_id', 'trade_flag'],
    schema='silver',
	on_schema_change='append_new_columns',
	indexes=[
		{'columns': ['trade_date', 'city_id', 'trade_country_id', 'product_category_id'], 'unique': True},
		
		{'columns': ['city_id']},
		{'columns': ['trade_country_id']},
		{'columns': ['product_category_id']}
	]
) }}

-- Bring the source bronze tables
with export_source as (
	select substring("noMunMinsgUf" for position(' - ' in "noMunMinsgUf"))	as "city_name"
		 , "year"
		 , "monthNumber"
		 , "country"
		 , regexp_replace(lower(unaccent("country")), '[^a-z]', '', 'g') 	as "country_name_norm"
		 , "state"
		 , "headingCode"
		 , "heading"
		 , "metricFOB"
		 , "metricKG"
		 , "ingested_at"
		 , "loaded_at"
		 , row_number() over (
            partition by "noMunMinsgUf", "year", "monthNumber", "country", "headingCode"
            order by "loaded_at" desc
           ) as "row_num"
      from {{ source('bronze', 'fish_trade_export') }}
),
cities_source as (
	select "id"
	 	 , substring("text" for position(' - ' in "text"))	as "city_name"
	 	 , "noMunMin"
	  from {{ source('bronze', 'cities') }}
),
countries_source as (
	select "id"
         , "text"
        -- Normalize column text, leaving only letters
         , regexp_replace(lower(unaccent("text")), '[^a-z]', '', 'g') 	as country_name_norm
	  from {{ source('bronze', 'countries') }}
),

-- Join exports with cities
joined as (
	select e.*
		 , c."id" as "city_id"
		 , p."id" as "country_id"
	  from export_source 	e
	  left
	  join cities_source 	c on e."city_name" = c."city_name"
	  left
	  join countries_source p on e."country_name_norm" = p."country_name_norm"
),

-- Apply transformations
transformed as (
    select 
		   -- Date column with null treatment
		   to_date(
				concat(
					coalesce("year", '1900'), '/'
				  , coalesce("monthNumber", '01'), '/'
				  , '01'
				)
			  , 'YYYY/MM/DD'
		   )								as "trade_date"

		   -- Apply null treatments 
		 , coalesce("city_id", 'N/A')		as "city_id"
		 , coalesce("country_id", 'N/A')	as "trade_country_id"
		 , coalesce("headingCode", '0000')	as "product_category_id"
		 , coalesce("metricFOB", '0')		as "fob_value"
		 , coalesce("metricKG", '0')		as "net_weight"

		   -- Flag column specifying the trade (imp or exp)
		 , 'exp'							as "trade_flag"
		 , "ingested_at"
		 , "loaded_at"
		 , "row_num"
      from joined
),

-- Defined types
final as (
	select "trade_date"::date
		 , "city_id"::varchar(50)
		 , "trade_country_id"::varchar(4)
		 , "product_category_id"::char(4)
		 , "fob_value"::decimal(20,2)
		 , "net_weight"::decimal(20,2)

	 	   -- Quality flags
	 	 , case when "fob_value"::decimal(20,2)  > 0 then true else false end	as "is_valid_value"
	 	 , case when "net_weight"::decimal(20,2) > 0 then true else false end	as "is_valid_weight"

		 , "trade_flag"::char(3)
		 , "ingested_at"::timestamp
		 , "loaded_at"::timestamp
		 , "row_num"::integer
	  from transformed
)

-- Final querie with cleaned data
select "trade_date"
	 , "city_id"
	 , "trade_country_id"
	 , "product_category_id"
	 , "fob_value"
	 , "net_weight"
	 , "trade_flag"
	 , "ingested_at"
	 , "loaded_at"
	 , timestamp as "processed_at"
  from final
 where "row_num" 			= 1
   and "is_valid_value" 	= true
   and "is_valid_weight" 	= true

-- Run incremental ingestion, if table already exists, if not, run full ingestion
{% if is_incremental() %}

  and "trade_date" >= (select coalesce(max("trade_date"), '1900-01-01') from {{ this }})

{% endif %}