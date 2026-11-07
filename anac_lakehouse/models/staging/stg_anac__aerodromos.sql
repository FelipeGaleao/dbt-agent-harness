{{ config(materialized='view') }}

WITH source_data AS (
    SELECT
        "CODIGO_OACI" AS codigo_oaci,
        "CIAD" AS ciad,
        "NOME" AS nm_aeroporto,
        "MUNICIPIO_ATENDIDO" AS nm_municipio_atendido,
        "UF" AS cd_uf,
        "LATITUDE" AS ds_latitude,
        "LONGITUDE" AS ds_longitude,
        "ALTITUDE" AS ds_altitude,
        "OPERACAO" AS ds_operacao,
        "SITUACAO" AS ds_situacao,
        "SITUADO_NA_AMAZONIA_LEGAL" AS ds_situado_amazonia_legal
    FROM
        {{ ref('landing_aerodromos') }}
)

SELECT
    codigo_oaci,
    ciad,
    nm_aeroporto,
    nm_municipio_atendido,
    cd_uf,
    ds_latitude,
    ds_longitude,
    ds_altitude,
    ds_operacao,
    ds_situacao,
    CASE WHEN ds_situado_amazonia_legal = 'X' THEN TRUE ELSE FALSE END AS is_situado_amazonia_legal
FROM
    source_data
