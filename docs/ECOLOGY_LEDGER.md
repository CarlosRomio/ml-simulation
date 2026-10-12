# Auditoria ecológica por estoque e fluxo

## Objetivo

`results/ecosystem_experiment/ecology_history.csv` registra o estado do estoque de plantas e os eventos ecológicos de cada passo. A série foi criada para auditar as regras do ambiente, não para avaliar a inteligência ou a sobrevivência dos agentes.

## Granularidade e ordem temporal

- Há uma linha inicial por execução (`step=0`), antes da simulação avançar.
- Cada linha de `step=N` contém o estoque observado **depois** das ações de agentes e da atualização ambiental daquele passo.
- Os campos de evento na linha `N` contabilizam eventos ocorridos durante o passo `N`, incluindo coleta, transições de crescimento e tentativa de regeneração.
- `run` identifica a execução e `seed` permite reproduzi-la.

## Campos de estoque

- `seeds`, `growing`, `mature`: plantas por estágio.
- `total`: total de plantas, que deve ser igual à soma dos três estágios.
- `water_sources`: quantidade de fontes de água permanentes no mapa. Água ainda não é um estoque finito.

## Campos de fluxo

- `plants_seed_to_growing`: transições de semente para crescimento.
- `plants_growing_to_mature`: transições para planta madura.
- `plants_collected_by_humans`, `plants_collected_by_herbivores`: plantas removidas do mapa pela coleta.
- `food_items_collected_by_humans`: itens legados da classe `Food`, separados das plantas.
- `water_drinks_*`: eventos de beber registrados para cada espécie.
- `water_thirst_reduction_*`: redução efetiva da variável de sede. **Não representa unidades físicas de água retiradas da fonte**; as fontes atuais são permanentes e ilimitadas.
- Em `humans.csv`, `water_thirst_reduction` é o nome explícito para a métrica legada `water_units_consumed`, que mede a mesma redução de sede.
- Em `human_physiology_history.csv`, `drank_water`, `water_thirst_reduction` e `collected_resource_type` distinguem ingestão de água, efeito fisiológico e tipo de recurso coletado.
- `seeds_spawn_requested`: quantidade de sementes solicitadas pelo gerador naquele passo.
- `seeds_spawned`: sementes realmente criadas.
- `seeds_blocked_by_plant_cap`: solicitações que excederam o limite de plantas.
- `seeds_blocked_by_space`: solicitações que cabiam no limite de plantas, mas não encontraram células elegíveis.

## Invariantes auditáveis

Para cada linha:

`total = seeds + growing + mature`

Para cada passo de regeneração:

`seeds_spawn_requested = seeds_spawned + seeds_blocked_by_plant_cap + seeds_blocked_by_space`

Entre o estoque de plantas de dois passos consecutivos:

`total_atual = total_anterior + seeds_spawned - plants_collected_by_humans - plants_collected_by_herbivores`

A última relação pressupõe que a única criação de plantas seja a geração de sementes e que humanos/herbívoros sejam os únicos coletores de plantas, conforme a mecânica atual. Se novas formas de remoção ou criação forem adicionadas, o ledger e os testes deverão ser atualizados no mesmo incremento.

## Limitações conhecidas, intencionais nesta etapa

1. Água é uma fonte permanente; não há volume finito, contaminação ou sazonalidade.
2. Plantas representam uma unidade por célula; não há biomassa, quantidade de alimento ou qualidade nutricional variável.
3. A regeneração cria sementes aleatoriamente em células elegíveis, sem dispersão espacial a partir de plantas adultas.
4. A série registra eventos agregados por espécie, não um identificador individual para cada recurso. Para auditar a dinâmica atual, isso é suficiente; eventos individuais poderão ser adicionados quando recursos transportáveis e armazenamento forem implementados.
5. A atualização de plantas ocorre ao final do passo. Alterar essa ordem pode alterar a disponibilidade de plantas maduras e deve ser coberto por testes de regressão.
