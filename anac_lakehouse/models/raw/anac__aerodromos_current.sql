{{ config(
    materialized='table',
    schema='raw'
) }}

with timeline as (
    select * from {{ ref('anac__aerodromos_timeline') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by OACI
            order by loaded_at desc
        ) as rn
    from timeline
)

select
    OACI, -- Chave Primária
    aerodrome_hash,
    loaded_at as last_updated_at,
    snapshot_date,
    CODIGO_OACI,
    CIAD,
    NOME,
    MUNICIPIO_ATENDIDO,
    UF,
    LATITUDE,
    LONGITUDE,
    ALTITUDE,
    OPERACAO,
    AIP_BRASIL,
    DESIGNACAO,
    COMPRIMENTO,
    LARGURA,
    RESISTENCIA,
    SUPERFICIE,
    DESIGNACAO_2,
    COMPRIMENTO_2,
    LARGURA_2,
    RESISTENCIA_2,
    SUPERFICIE_2,
    DESIGNACAO_3,
    COMPRIMENTO_3,
    LARGURA_3,
    RESISTENCIA_3,
    SUPERFICIE_3,
    RAMPAS_DE_APROXIMACAO,
    FORMATO_DA_AREA_DE_POUSO,
    DIMENSOES,
    RESISTENCIA_4,
    SUPERFICIE_4,
    P1,
    P2,
    P3,
    P4,
    PORTARIAS,
    COLUNA_36,
    COLUNA_37,
    COLUNA_38,
    "PORTARIA_N_189672026_E_ALTERACOES",
    "PORTARIA_N_173882025_A_CLASSE_I_SE_DIVIDE_AINDA_EM_RBAC_121_RBAC_135_REGULAR_E_OUTRAS_OPERACOES",
    "PORTARIA_N_20072014_E_ALTERACOES_=_REGIME_TARIFARIO_DIFERENCIADO",
    AERONAVE_CRITICA,
    TIPO_DE_APROX_CABECEIRAS,
    CAT_SESCINC,
    R1,
    R2,
    REFERENCIAS,
    RESTRICAOOES,
    SITUACAO,
    R1_2,
    REFERENCIA,
    SITUADO_NA_AMAZONIA_LEGAL,
    OBSERVACOES
from ranked
where rn = 1
