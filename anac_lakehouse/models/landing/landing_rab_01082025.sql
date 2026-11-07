{{ config(
    materialized='table',
    schema='landing'
) }}

/*
    Model: landing_rab_01082025
    Camada: Landing
    Origem: seed rab_01082025
    Objetivo: Tabela de pouso dos dados brutos do RAB (snapshot de 01/08/2025).
*/

select * from {{ ref('rab_01082025') }}

