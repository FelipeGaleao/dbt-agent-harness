{{ config(
    materialized='table',
    schema='trusted'
) }}

WITH stg_aerodromos AS (
    SELECT
        codigo_oaci,
        nm_aeroporto,
        nm_municipio_atendido,
        cd_uf,
        ds_latitude,
        ds_longitude,
        ds_altitude,
        ds_operacao,
        ds_situacao,
        is_situado_amazonia_legal
    FROM
        {{ ref('stg_anac__aerodromos') }}
)

SELECT
    codigo_oaci AS id_aeroporto, -- Primary Key: ICAO code for the airport
    nm_aeroporto,
    nm_municipio_atendido AS nm_municipio,
    cd_uf,
    ds_latitude AS latitude,
    ds_longitude AS longitude,
    TRY_CAST(REPLACE(ds_altitude, ' m', '') AS INTEGER) AS altitude_m,
    ds_operacao,
    ds_situacao,
    is_situado_amazonia_legal
FROM
    stg_aerodromos
