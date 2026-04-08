{#
  Macro: generate_schema_name (override do padrão DBT)
  Purpose: Sobrescreve o comportamento padrão do DBT de prefixar o schema com o
           nome do target (ex: "dev_bronze"). Neste projeto, o schema configurado
           em dbt_project.yml (bronze, silver, gold) é usado diretamente, sem prefixo.
  Behavior:
    - Se `custom_schema_name` for None → usa o schema default do target (profiles.yml)
    - Se `custom_schema_name` for definido → usa exatamente esse valor (sem prefixo)
  Example:
    - Model com schema: 'gold' → cria em schema 'gold' (não 'dev_gold')
#}
{% macro generate_schema_name(custom_schema_name, node) -%}

    {%- set default_schema = target.schema -%}

    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}

{%- endmacro %}