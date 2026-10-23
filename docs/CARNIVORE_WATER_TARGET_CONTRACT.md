# Integração do contrato de objetivos na busca por água dos carnívoros

## Escopo

A integração usa `TargetSelector.select_reachable_target()` para selecionar fontes de água alcançáveis e reutiliza a rota retornada por `NavigationService`. A busca estática adicional fica desativada neste fluxo (`capture_static_path=False`), evitando duas buscas de caminho para a mesma fonte.

## Política preservada

A ordem de decisão permanece a existente em `Carnivore.choose_action()`:

1. Se a sede é `>= 50`, tenta água primeiro quando existem fontes.
2. Se não há fontes de água nessa primeira consulta, considera presas quando a fome é `>= 30`.
3. Se não há candidatos de caça e a sede é `>= 35`, tenta água como fallback.
4. A perseguição de presas continua usando a regra específica do carnívoro: ao ficar adjacente, aguarda o sistema de combate.
5. Se uma fonte existe, mas não é alcançável com sede alta, o fluxo não muda para caça automaticamente; esse comportamento anterior foi preservado intencionalmente nesta refatoração.

O contrato compartilha seleção técnica e status de navegação, não redefine a política de sede, fome, caça, fuga, descanso ou exploração.

## Validação

`tests/test_water_search_characterization.py` cobre a prioridade de água sobre presa com sede alta, a prioridade de caça abaixo do limiar alto, o fallback de água a partir de sede 35, o uso do contrato e o caso de fonte de água inalcançável.
