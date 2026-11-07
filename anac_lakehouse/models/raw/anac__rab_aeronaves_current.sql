{{ config(
    materialized='table',
    schema='raw'
) }}

with timeline as (
    select * from {{ ref('anac__rab_aeronaves_timeline') }}
),

ranked as (
    select
        *,
        row_number() over (
            partition by MARCAS
            order by loaded_at desc
        ) as rn
    from timeline
)

select
    row_hash,
    snapshot_date,
    loaded_at as last_updated_at,
    MARCAS,
    PROPRIETARIOS,
    OPERADORES,
    NR_CERT_MATRICULA,
    NR_SERIE,
    CD_TIPO,
    DS_MODELO,
    NM_FABRICANTE,
    CD_CLS,
    NR_PMD,
    CD_TIPO_ICAO,
    NR_TRIPULACAO_MIN,
    NR_PASSAGEIROS_MAX,
    NR_ASSENTOS,
    NR_ANO_FABRICACAO,
    DT_VALIDADE_CVA,
    DT_VALIDADE_CA,
    DT_CANC,
    DS_MOTIVO_CANC,
    CD_INTERDICAO,
    DS_GRAVAME,
    DT_MATRICULA,
    TP_MOTOR,
    QT_MOTOR,
    TP_POUSO,
    TP_CA,
    CD_PROPOSITO_CAVE,
    NM_PROPOSITO_CAVE,
    CF_OPERACIONAL,
    DS_CATEGORIA_HOMOLOGACAO,
    TP_OPERACAO,
    DT_VENDA,
    DS_MOEDA,
    NR_PRECO_VENDA
from ranked
where rn = 1

