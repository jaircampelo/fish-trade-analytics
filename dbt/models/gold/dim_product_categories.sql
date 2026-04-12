{{ config(
    materialized='table',
    schema='gold',
) }}

select product_category_id::char(4)         as product_category_id
     , product_category_name::varchar(100)  as product_category_name
     , product_category_description::text   as product_category_description
  from {{ ref('seed_product_categories') }}