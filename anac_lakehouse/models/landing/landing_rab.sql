{{ config(
    materialized='table',
    schema='landing'
) }}

select * from {{ ref('rab_07112026') }}


