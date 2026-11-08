{{ config(
    materialized='incremental',
    schema='raw',
    unique_key='aerodrome_hash',
    on_conflict='update'
) }}

with source_data as (
    select * from {{ ref('landing_aerodromos') }}
),

transformed as (
    select
        -- Gera um hash do registro completo para detecção de mudanças / unicidade
        md5(
            concat_ws(
                '||',
                coalesce(CODIGO_OACI, ''),
                coalesce(CIAD, ''),
                coalesce(NOME, ''),
                coalesce(MUNICIPIO_ATENDIDO, ''),
                coalesce(UF, ''),
                coalesce(LATITUDE, ''),
                coalesce(LONGITUDE, ''),
                coalesce(ALTITUDE, ''),
                coalesce(OPERACAO, ''),
                coalesce(OACI, ''),
                coalesce(AIP_BRASIL, ''),
                coalesce(DESIGNACAO, ''),
                coalesce(COMPRIMENTO, ''),
                coalesce(LARGURA, ''),
                coalesce(RESISTENCIA, ''),
                coalesce(SUPERFICIE, ''),
                coalesce(DESIGNACAO_2, ''),
                coalesce(COMPRIMENTO_2, ''),
                coalesce(LARGURA_2, ''),
                coalesce(RESISTENCIA_2, ''),
                coalesce(SUPERFICIE_2, ''),
                coalesce(DESIGNACAO_3, ''),
                coalesce(COMPRIMENTO_3, ''),
                coalesce(LARGURA_3, ''),
                coalesce(RESISTENCIA_3, ''),
                coalesce(SUPERFICIE_3, ''),
                coalesce(RAMPAS_DE_APROXIMACAO, ''),
                coalesce(FORMATO_DA_AREA_DE_POUSO, ''),
                coalesce(DIMENSOES, ''),
                coalesce(RESISTENCIA_4, ''),
                coalesce(SUPERFICIE_4, ''),
                coalesce(P1, ''),
                coalesce(P2, ''),
                coalesce(P3, ''),
                coalesce(P4, ''),
                coalesce(PORTARIAS, ''),
                coalesce(COLUNA_36, ''),
                coalesce(COLUNA_37, ''),
                coalesce(COLUNA_38, ''),
                coalesce("PORTARIA_N_189672026_E_ALTERACOES", ''), -- Aspas para nomes problemáticos
                coalesce("PORTARIA_N_173882025_A_CLASSE_I_SE_DIVIDE_AINDA_EM_RBAC_121_RBAC_135_REGULAR_E_OUTRAS_OPERACOES", ''), -- Aspas
                coalesce("PORTARIA_N_20072014_E_ALTERACOES_=_REGIME_TARIFARIO_DIFERENCIADO", ''), -- Aspas
                coalesce(AERONAVE_CRITICA, ''),
                coalesce(TIPO_DE_APROX_CABECEIRAS, ''),
                coalesce(cast(CAT_SESCINC as varchar), ''),
                coalesce(R1, ''),
                coalesce(R2, ''),
                coalesce(REFERENCIAS, ''),
                coalesce(RESTRICAOOES, ''),
                coalesce(SITUACAO, ''),
                coalesce(R1_2, ''),
                coalesce(REFERENCIA, ''),
                coalesce(SITUADO_NA_AMAZONIA_LEGAL, ''),
                coalesce(OBSERVACOES, '')
            )
        ) as aerodrome_hash,
        
        -- Metadados de carga e linhagem temporal
        current_date as snapshot_date,
        current_timestamp as loaded_at,

        -- Colunas originais da landing_aerodromos
        CODIGO_OACI,
        CIAD,
        NOME,
        MUNICIPIO_ATENDIDO,
        UF,
        LATITUDE,
        LONGITUDE,
        ALTITUDE,
        OPERACAO,
        OACI,
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
    from source_data
),

deduped as (
    -- Elimina duplicatas idênticas oriundas do mesmo snapshot
    select *,
        row_number() over (
            partition by OACI, aerodrome_hash -- Inclui OACI no partition by para garantir unicidade por aeródromo + hash
            order by loaded_at
        ) as dedup_rank
    from transformed
)

select * exclude (dedup_rank)
from deduped
where dedup_rank = 1

{% if is_incremental() %}
  -- Em cargas incrementais futuras, insere apenas registros cujos hashes não existam na timeline
  and aerodrome_hash not in (select aerodrome_hash from {{ this }})
{% endif %}
