{{ config(
    materialized='view',
    schema='staging'
) }}

/*
    Model: stg_anac__rab_aeronaves
    Camada: Staging
    Papel: Limpeza, tipagem (casting resiliente), padronização e renomeação de colunas 1:1 com a fonte raw.
           NENHUMA agregação de negócio ou feature complexa deve ser computada aqui.
*/

with source as (
    select * from {{ ref('anac__rab_aeronaves_current') }}
),

renamed_and_casted as (
    select
        -- 1. Chaves de Identificação Naturais
        upper(trim(MARCAS)) as cd_marca_aeronave,
        nullif(trim(NR_CERT_MATRICULA), '') as nr_certificado_matricula,
        nullif(trim(NR_SERIE), '') as nr_serie,

        -- 2. Atributos Descritivos e Especificações Técnicas
        upper(nullif(trim(NM_FABRICANTE), '')) as nm_fabricante,
        upper(nullif(trim(DS_MODELO), '')) as ds_modelo,
        upper(nullif(trim(CD_TIPO_ICAO), '')) as cd_tipo_icao,
        upper(nullif(trim(CD_TIPO), '')) as cd_tipo_aeronave,
        upper(nullif(trim(CD_CLS), '')) as cd_classe,
        upper(nullif(trim(TP_MOTOR), '')) as tp_motor,
        upper(nullif(trim(TP_POUSO), '')) as tp_pouso,
        upper(nullif(trim(CF_OPERACIONAL), '')) as ds_classificacao_operacional,
        upper(nullif(trim(DS_CATEGORIA_HOMOLOGACAO), '')) as ds_categoria_homologacao,
        upper(nullif(trim(TP_OPERACAO), '')) as tp_operacao,

        -- 3. Métricas Físicas e Capacidades Operacionais (Parsing Resiliente)
        try_cast(QT_MOTOR as integer) as qt_motores,
        try_cast(NR_PASSAGEIROS_MAX as integer) as qt_passageiros_max,
        try_cast(NR_TRIPULACAO_MIN as integer) as qt_tripulacao_min,
        try_cast(NR_ASSENTOS as integer) as qt_assentos_total,
        try_cast(NR_ANO_FABRICACAO as integer) as nr_ano_fabricacao,

        -- Limpeza de PMD com unidades de texto (ex.: 585Kg, 450 Kg, 2721,5)
        case
            when NR_PMD is null or trim(NR_PMD) = '' then null
            else try_cast(
                replace(
                    replace(
                        regexp_extract(trim(NR_PMD), '([0-9]+(?:[.,][0-9]+)?)', 1),
                        '.', ''
                    ),
                    ',', '.'
                ) as double
            )
        end as nr_pmd_kg,

        -- 4. Marcos Temporais (Tratamento de múltiplos formatos e datas anômalas)
        coalesce(
            try_strptime(left(trim(DT_MATRICULA), 10), '%Y-%m-%d'),
            try_strptime(trim(DT_MATRICULA), '%d/%m/%Y'),
            try_strptime(trim(DT_MATRICULA), '%d%m%Y')
        )::date as dt_matricula,

        coalesce(
            try_strptime(trim(DT_VALIDADE_CA), '%d%m%Y'),
            try_strptime(trim(DT_VALIDADE_CA), '%d%m%y'),
            try_strptime(trim(DT_VALIDADE_CA), '%d/%m/%Y'),
            try_strptime(left(trim(DT_VALIDADE_CA), 10), '%Y-%m-%d')
        )::date as dt_validade_ca,

        coalesce(
            try_strptime(trim(DT_VALIDADE_CVA), '%d%m%Y'),
            try_strptime(trim(DT_VALIDADE_CVA), '%d%m%y'),
            try_strptime(trim(DT_VALIDADE_CVA), '%d/%m/%Y'),
            try_strptime(left(trim(DT_VALIDADE_CVA), 10), '%Y-%m-%d')
        )::date as dt_validade_cva,

        coalesce(
            try_strptime(trim(DT_CANC), '%d/%m/%Y'),
            try_strptime(trim(DT_CANC), '%d%m%Y'),
            try_strptime(left(trim(DT_CANC), 10), '%Y-%m-%d')
        )::date as dt_cancelamento,

        coalesce(
            try_strptime(trim(DT_VENDA), '%d%m%Y'),
            try_strptime(trim(DT_VENDA), '%d%m%y'),
            try_strptime(trim(DT_VENDA), '%d/%m/%Y'),
            try_strptime(left(trim(DT_VENDA), 10), '%Y-%m-%d')
        )::date as dt_venda,

        -- 5. Informações Legais, Gravames e Interdições
        upper(nullif(trim(DS_MOTIVO_CANC), '')) as ds_motivo_cancelamento,
        upper(nullif(trim(DS_GRAVAME), '')) as ds_gravame,
        upper(nullif(trim(CD_INTERDICAO), '')) as cd_interdicao,

        -- 6. Estruturas Documentais / Relacionamentos
        PROPRIETARIOS as proprietarios_json,
        OPERADORES as operadores_json,

        -- 7. Dados Comerciais
        nullif(trim(DS_MOEDA), '') as cd_moeda_venda,
        case
            when NR_PRECO_VENDA is null or trim(NR_PRECO_VENDA) = '' then null
            else try_cast(
                replace(
                    replace(trim(NR_PRECO_VENDA), '.', ''),
                    ',', '.'
                ) as double
            )
        end as vl_preco_venda,

        -- 8. Metadados Técnicos de Linhagem
        row_hash,
        snapshot_date,
        last_updated_at

    from source
)

select * from renamed_and_casted

