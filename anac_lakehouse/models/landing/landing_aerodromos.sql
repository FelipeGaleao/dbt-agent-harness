{{ config(
    materialized='table',
    schema='landing'
) }}

/*
    Model: landing_aerodromos
    Camada: Landing
    Origem: seed aerodromos_publicos
    Objetivo: Tabela de pouso dos dados brutos de aeródromos civis públicos da ANAC.
*/

select * from {{ ref('aerodromos_publicos') }}

