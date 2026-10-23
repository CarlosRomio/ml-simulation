# Navegação: posição inicial que deixou de ser transitável

## Evidência

A auditoria `ecosystem_audit_navigation_observability`, com sementes 7200–7207 e 3.000 passos por execução, registrou 108 resultados `INVALID_START`, todos na execução da semente 7204.

## Causa arquitetural

`NavigationService.plan_route()` rejeitava uma posição inicial não transitável. Porém, o BFS existente aceita a posição inicial como ponto de partida e permite sair dela. Essa diferença é relevante quando uma célula se torna não transitável enquanto uma entidade já está nela — por exemplo, quando uma planta muda para o estado `GROWING`, cuja célula não é transitável.

O contrato deve validar os limites do mundo para a posição inicial e exigir transitabilidade para o destino. A posição atual pode ser não transitável e ainda assim permitir uma rota de saída.

## Alteração

- Removida a rejeição antecipada da posição inicial apenas por `world.is_walkable(*start) == False`.
- Mantidas as validações de limites, destino transitável, ocupação dinâmica e ausência de rota.
- Adicionado teste de caracterização com uma planta em estado `GROWING` na posição inicial.
- Não foram alteradas políticas de seleção de alvo ou prioridades comportamentais.

## Validação

Suíte executada no pacote de trabalho: `262 passed, 1 skipped`.

A auditoria ecológica completa deve ser repetida após esta correção para verificar se os 108 `INVALID_START` desaparecem e para medir qualquer efeito no comportamento. A hipótese da planta em crescimento explica a incompatibilidade do contrato, mas a confirmação da origem exata das 108 ocorrências requer repetir a auditoria ou registrar a razão por ocorrência.
