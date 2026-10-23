# Correção da instrumentação de progresso dos alvos

## Problema identificado na auditoria

A auditoria anterior registrou episódios dos carnívoros como `EXPLORATION` mesmo durante a caça, porque `Carnivore` não possui o atributo `target_intent` esperado pelo coletor. Os herbívoros também eram agrupados em `SEEK_RESOURCE`, pois o coletor usava um valor padrão em vez de inferir o tipo do recurso selecionado.

## Correção

- Carnívoros: o coletor classifica alvos ativos como `HUNT` ou `SEEK_WATER`; quando não há alvo ativo, usa o `exploration_target` persistente para medir patrulha como `EXPLORATION`.
- Herbívoros: a intenção observada é derivada do recurso capturado antes da ação: `SEEK_WATER` para água e `SEEK_FOOD` para alimento maduro.
- A instrumentação continua observacional: nenhuma regra de decisão, limiar, recompensa ou prioridade foi alterada.

## Validação

- Suíte: 285 testes passaram, 1 ignorado.
- Auditoria piloto: mundo 100 × 100, 1 execução, 100 passos; os resumos passaram a distinguir exploração, caça, busca por água e busca por alimento quando esses alvos ocorreram.

## Próximo passo

Reexecutar a auditoria de referência de 100 × 100 com 8 execuções, 3.000 passos, seed inicial 7200, `--workers 14` (ou 8, se quiser reproduzir exatamente o paralelismo recomendado anteriormente) e `--sample-every 20`. Não comparar diretamente as taxas de progresso por intenção da auditoria anterior, pois essas categorias estavam incorretas.
