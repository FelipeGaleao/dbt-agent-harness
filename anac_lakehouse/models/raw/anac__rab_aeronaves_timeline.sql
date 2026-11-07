{{ config(
    materialized='incremental',
    schema='raw',
    unique_key='row_hash'
) }}

with source_data as (
    select * from {{ ref('landing_rab') }}
),

transformed as (
    select
        -- Gera um hash do registro completo para detecção de mudanças / unicidade
        md5(
            concat_ws(
                '||',
                coalesce(MARCAS, ''),
                coalesce(NR_CERT_MATRICULA, ''),
                coalesce(NR_SERIE, ''),
                coalesce(CD_TIPO, ''),
                coalesce(DS_MODELO, ''),
                coalesce(NM_FABRICANTE, ''),
                coalesce(CD_CLS, ''),
                coalesce(NR_PMD, ''),
                coalesce(CD_TIPO_ICAO, ''),
                coalesce(cast(NR_TRIPULACAO_MIN as varchar), ''),
                coalesce(cast(NR_PASSAGEIROS_MAX as varchar), ''),
                coalesce(cast(NR_ASSENTOS as varchar), ''),
                coalesce(NR_ANO_FABRICACAO, ''),
                coalesce(DT_VALIDADE_CVA, ''),
                coalesce(DT_VALIDADE_CA, ''),
                coalesce(DT_CANC, ''),
                coalesce(DS_MOTIVO_CANC, ''),
                coalesce(CD_INTERDICAO, ''),
                coalesce(DS_GRAVAME, ''),
                coalesce(DT_MATRICULA, ''),
                coalesce(TP_MOTOR, ''),
                coalesce(cast(QT_MOTOR as varchar), ''),
                coalesce(TP_POUSO, ''),
                coalesce(TP_CA, ''),
                coalesce(CD_PROPOSITO_CAVE, ''),
                coalesce(NM_PROPOSITO_CAVE, ''),
                coalesce(CF_OPERACIONAL, ''),
                coalesce(DS_CATEGORIA_HOMOLOGACAO, ''),
                coalesce(TP_OPERACAO, ''),
                coalesce(DT_VENDA, ''),
                coalesce(DS_MOEDA, ''),
                coalesce(NR_PRECO_VENDA, ''),
                coalesce(PROPRIETARIOS, ''),
                coalesce(OPERADORES, '')
            )
        ) as row_hash,
        
        -- Metadados de carga e linhagem temporal
        current_date as snapshot_date,
        current_timestamp as loaded_at,

        -- Atributos originais da aeronave
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

    from source_data
),

deduped as (
    -- Elimina duplicatas idênticas oriundas do mesmo snapshot
    select *,
        row_number() over (
            partition by MARCAS, row_hash
            order by loaded_at
        ) as dedup_rank
    from transformed
)

select
    row_hash,
    snapshot_date,
    loaded_at,
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
from deduped
where dedup_rank = 1

{% if is_incremental() %}
  -- Em cargas incrementais futuras, insere apenas registros cujos hashes não existam na timeline
  and row_hash not in (select row_hash from {{ this }})
{% endif %}

