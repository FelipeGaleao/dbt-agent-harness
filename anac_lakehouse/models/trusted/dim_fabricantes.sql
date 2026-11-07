{{ config(
    materialized='incremental',
    unique_key='id_fabricante',
    schema='trusted'
) }}

WITH stg_aeronaves AS (
    SELECT
        nm_fabricante
    FROM {{ ref('stg_anac__rab_aeronaves') }}
    WHERE nm_fabricante IS NOT NULL
    GROUP BY nm_fabricante
),

dim_fabricantes_aeronaves AS (
    SELECT
        md5(nm_fabricante) AS id_fabricante,
        nm_fabricante
    FROM stg_aeronaves
)

SELECT * FROM dim_fabricantes_aeronaves