
{{ config(
    materialized='table',
    schema='trusted'
) }}

/*
    Model: dim_proprietario
    Pattern: Entity-Centric Data Modeling (ECM)
    Granularidade: 1 linha por proprietário (Chave natural: cpf_cnpj_proprietario)
    Origem: stg_anac__rab_aeronaves
    Objetivo: Consolidar informações de proprietários de aeronaves, agregando
              suas aeronaves e valores associados.
*/

WITH stg_aeronaves AS (
    SELECT
        cd_marca_aeronave AS marca_aeronave,
        cd_tipo_icao,
        proprietarios_json,
        vl_preco_venda,
        cd_moeda_venda
    FROM {{ ref('stg_anac__rab_aeronaves') }}
),

unpacked_proprietarios AS (
    SELECT
        a.marca_aeronave,
        a.cd_tipo_icao,
        a.vl_preco_venda,
        a.cd_moeda_venda,
        -- Desaninhar o array de proprietários
        json_extract(prop.value, '$.DOCUMENTO') AS nr_cpf_cnpj_proprietario,
        json_extract(prop.value, '$.NOME') AS nm_proprietario,
        json_extract(prop.value, '$.UF') AS cd_uf_proprietario
    FROM
        stg_aeronaves a,
        json_each(a.proprietarios_json) AS prop
),

cleaned_proprietarios AS (
    SELECT
        -- Extrair apenas dígitos para sk_proprietario e remover aspas duplas
        REPLACE(REGEXP_REPLACE(nr_cpf_cnpj_proprietario, '[^0-9]', ''), '"', '') AS sk_proprietario_raw,
        REPLACE(nm_proprietario, '"', '') AS nm_proprietario,
        REPLACE(cd_uf_proprietario, '"', '') AS cd_uf_proprietario,
        marca_aeronave,
        cd_tipo_icao,
        vl_preco_venda,
        cd_moeda_venda
    FROM unpacked_proprietarios
    WHERE nr_cpf_cnpj_proprietario IS NOT NULL
),

validated_proprietarios AS (
    SELECT
        sk_proprietario_raw AS sk_proprietario,
        nm_proprietario,
        cd_uf_proprietario,
        marca_aeronave,
        cd_tipo_icao,
        vl_preco_venda,
        cd_moeda_venda
    FROM cleaned_proprietarios
    WHERE LENGTH(sk_proprietario_raw) = 11 OR LENGTH(sk_proprietario_raw) = 14
)
,
grouped_proprietarios AS (
    SELECT
        sk_proprietario,
        ANY_VALUE(nm_proprietario) AS nm_proprietario,
        ANY_VALUE(cd_uf_proprietario) AS cd_uf_proprietario,
        -- Inferir tipo de proprietário (CPF 11 digitos, CNPJ 14 digitos)
        CASE
            WHEN LENGTH(sk_proprietario) = 11 THEN 'PESSOA_FISICA'
            WHEN LENGTH(sk_proprietario) = 14 THEN 'PESSOA_JURIDICA'
            ELSE 'DESCONHECIDO' -- Deveria ser minimizado por conta do filtro em validated_proprietarios
        END AS tp_proprietario,
        LIST(DISTINCT marca_aeronave) AS lista_aeronaves_matricula,
        LIST(DISTINCT cd_tipo_icao) AS lista_aeronaves_icao,
        COUNT(DISTINCT marca_aeronave) AS qtd_aeronaves,
        SUM(vl_preco_venda) AS vl_total_aeronaves,
        ANY_VALUE(cd_moeda_venda) AS cd_moeda_venda -- Assumindo uma moeda principal para a soma, pode ser refinado
    FROM validated_proprietarios
    GROUP BY
        sk_proprietario
)

SELECT * FROM grouped_proprietarios