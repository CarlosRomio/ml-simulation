# Revisão do contrato compartilhado de objetivos e navegação

**Escopo:** revisão estática da versão que integra a busca por água dos humanos, herbívoros e carnívoros. Esta revisão não altera regras comportamentais nem o código de execução.

## Resumo executivo

O contrato já separa duas responsabilidades úteis:

- `TargetSelector` ordena candidatos e tenta selecionar o primeiro que possui uma rota válida.
- `NavigationService` planeja a rota e retorna um `NavigationStatus` com um motivo técnico.

A separação é utilizável, mas há três pontos que precisam ser tratados antes de migrar a busca por alimento dos herbívoros:

1. A semântica de bloqueio temporário não é propagada de forma uniforme quando a ocupação dinâmica fica encapsulada em um `pathfinder` customizado.
2. O modo de diagnóstico do `TargetSelector` pode fazer buscas de caminho redundantes.
3. A persistência do alvo continua sendo uma política específica de cada espécie; isso é adequado, mas deve ser explicitado nos contratos de integração para não ser acidentalmente uniformizado.

A revisão inicial executou **273 testes aprovados e 1 ignorado**. A correção subsequente deste documento adicionou testes de contrato e executou **276 testes aprovados e 1 ignorado**. A alteração continua restrita à propagação dos bloqueios de navegação e à eliminação de uma busca estática redundante quando não há bloqueios; os limiares e as políticas comportamentais não foram alterados.

## 1. Semântica atual dos resultados

| Status | Significado observado no código | Observação |
|---|---|---|
| `PATH_FOUND` | Existe uma rota para um destino válido. | `path` inclui início e destino. |
| `ALREADY_AT_GOAL` | Início e destino são iguais e a célula de destino é transitável. | É sucesso; pode resultar em ação de permanecer no local. |
| `INVALID_START` | A posição inicial está fora dos limites do mundo. | Uma posição inicial dentro do mundo, mas que deixou de ser transitável, pode ser usada para sair dela. Isso é intencional. |
| `INVALID_GOAL` | Destino fora dos limites ou não transitável. | `GOAL_NOT_WALKABLE` cobre obstáculos e recursos que bloqueiam passagem, como planta em crescimento. |
| `TEMPORARILY_BLOCKED` | O destino está explicitamente ocupado ou as restrições dinâmicas impedem a rota enquanto uma rota sem essas restrições existe. | A classificação depende de os bloqueios dinâmicos serem passados explicitamente ao serviço. |
| `UNREACHABLE` | Não foi encontrada rota e a tentativa sem bloqueios dinâmicos também não demonstra uma rota alternativa. | Com um `pathfinder` customizado que esconde os bloqueios numa closure, pode ser impossível distinguir esse caso de um bloqueio temporário. |

### Detalhes importantes

- `TargetSelector.select_reachable_target()` percorre candidatos por distância Manhattan, depois por `y` e `x`; ele seleciona o primeiro alcançável nessa ordem. Não minimiza a distância real da rota entre todos os candidatos. Essa ordem é compatível com o comportamento atual e não deve ser alterada inadvertidamente.
- O seletor retorna imediatamente após o primeiro sucesso. `attempts` contém as tentativas até o candidato escolhido, não uma avaliação de todos os candidatos restantes.
- `ALREADY_AT_GOAL` é tratado como sucesso. O serviço verifica a transitabilidade do destino antes de verificar `start == goal`, portanto uma célula atual que deixou de ser transitável não é considerada um destino válido.
- Para pathfinders customizados, `NavigationService.find_path()` rejeita uma rota que cruza bloqueios dinâmicos; não consegue, por si só, pedir ao pathfinder customizado que procure uma rota alternativa, a menos que esse pathfinder já implemente essa regra.

## 2. Custo de planejamento

### Caminho com diagnóstico estático

`TargetSelector.select_reachable_target()` usa `capture_static_path=True` por padrão. Para cada candidato, isso executa `navigation.find_path()` sem restrições dinâmicas e, em seguida, `navigation.plan_route()`, que executa o planejamento efetivo.

No fluxo de água dos herbívoros, esse caminho estático é usado para identificar quais células ocupadas intersectam a rota estática e alimentar `blocked_steps`/diagnósticos de bloqueio. Portanto:

- sem posições bloqueadas, a busca estática adicional não contribui para `blocked_steps` e parece evitável sem mudar as métricas;
- com posições bloqueadas, a busca estática pode ser necessária para preservar a observabilidade atual, inclusive quando a rota dinâmica encontra um desvio;
- quando uma rota com bloqueios falha, `NavigationService.plan_route()` pode executar outra busca sem bloqueios para distinguir `TEMPORARILY_BLOCKED` de `UNREACHABLE`.

Assim, um candidato do herbívoro pode ocasionar duas buscas de caminho em condições normais e até três em um caso de bloqueio dinâmico sem rota disponível sob essas restrições. Humanos e carnívoros usam `capture_static_path=False` no fluxo de água e evitam a busca estática de diagnóstico.

### Recomendação de desempenho

Fazer profiling instrumentado antes de otimizações maiores, contando chamadas ao pathfinder e tempo por decisão. **Otimização localizada aplicada:** `TargetSelector` só calcula `static_path` quando a captura está habilitada e existe pelo menos uma posição bloqueada. Sem bloqueios, o planejamento efetivo é a única busca necessária. Quando existem bloqueios, a busca estática continua ativa para preservar `blocked_steps` e os diagnósticos existentes. Testes verificam uma chamada ao pathfinder no caso sem bloqueios e a preservação de `blocked_steps` no caso com bloqueios.

O tempo total de auditorias anteriores não é suficiente para atribuir variações de desempenho ao contrato, pois é sensível a condições de execução e não isola o custo do pathfinder.

## 3. Persistência de alvos por espécie

### Humanos (`Agent`)

- A seleção cognitiva compara `SEEK_WATER` com outras ações elegíveis; o contrato não escolhe a ação final.
- O alvo de água/comida é mantido entre decisões, mas o alvo fisiológico é invalidado periodicamente a cada cinco ticks de decisão para reavaliar alternativas.
- Se o próximo passo estiver ocupado, a rota é recalculada mantendo o alvo; se não houver rota, o alvo é limpo.
- Ao chegar à fonte de água, o agente permanece para beber.

### Herbívoros (`Herbivore`)

- A seleção de recursos é refeita a cada chamada de `choose_action()`.
- Água é considerada a partir de sede `>= 45`; alimento é considerado a partir de fome `>= 35`, com a prioridade da sede preservada pela ordem dos grupos.
- A fonte é escolhida de novo pela ordem Manhattan e pela alcançabilidade sob a ocupação atual. Uma fonte próxima que fica ocupada pode ser substituída por outra.
- Se nenhum recurso do grupo for alcançável, o alvo e a rota são limpos antes da exploração aleatória.

### Carnívoros (`Carnivore`)

- A seleção de água e presas é reavaliada em cada chamada de `choose_action()`; não há persistência equivalente à rota de exploração.
- Sede `>= 50` prioriza água. Se não houver candidatos de água, a política tenta presas quando fome `>= 30`; a busca de água de fallback ocorre a partir de sede `>= 35` quando não foram selecionadas presas.
- Se há água candidata em sede alta, mas todas as fontes são inalcançáveis, a política não cai automaticamente para caça; segue para exploração. Isso é comportamento sequencial existente e deve ser preservado.
- O alvo de exploração é persistente e tem histórico de posições recentes; essa persistência é distinta da seleção de água.

## 4. Inconsistência a resolver antes da busca por alimento

No fluxo humano, `choose_action()` encapsula ocupação dinâmica em um `pathfinder` customizado e depois passa esse callable pela camada `NavigationService`. A seleção de água constrói outro `NavigationService` ao redor do callable e não fornece `blocked_positions` explicitamente ao `plan_route()`.

Consequência: se o callable retornar `None` por causa de ocupação dinâmica, o serviço externo pode classificar o resultado como `UNREACHABLE`, pois não tem a informação explícita necessária para testar uma rota sem bloqueios e devolver `TEMPORARILY_BLOCKED`.

Isso não demonstra uma regressão comportamental nas auditorias já executadas, mas significa que os status diagnósticos não são semanticamente uniformes entre todos os usos do contrato.

**Correção aplicada nesta versão:** o fluxo humano conserva uma instância de `NavigationService` construída a partir do pathfinder original e passa `blocked_positions` explicitamente a `TargetSelector.select_reachable_target()`. O callable com bloqueios encapsulados continua disponível para os demais fluxos legados, mas não é usado para classificar a busca por água. Isso permite que `plan_route()` compare a rota com restrições e a rota estática e retorne `TEMPORARILY_BLOCKED` quando a ocupação for a causa, ou `UNREACHABLE` quando não houver rota mesmo sem esses bloqueios. A exceção de aproximação a presas permanece na política de movimento existente.

A correção tem teste de integração para uma posição com todas as saídas dinamicamente bloqueadas; o resultado deve ser `TEMPORARILY_BLOCKED` com motivo `OCCUPANCY_BLOCKS_ALL_ROUTES`. Também há testes para `INVALID_GOAL`, `UNREACHABLE`, `ALREADY_AT_GOAL` e rota alternativa.

## 5. Sequência recomendada

1. Corrigir a propagação explícita dos bloqueios dinâmicos no fluxo humano, adicionando testes para `TEMPORARILY_BLOCKED` versus `UNREACHABLE`.
2. Adicionar testes de contrato para destino inválido, bloqueio de destino, rota alternativa, impossibilidade estrutural e `ALREADY_AT_GOAL`.
3. Medir chamadas e tempo do pathfinder, separando busca estática de diagnóstico e planejamento com restrições.
4. Só então migrar a seleção de alimento dos herbívoros, preservando limiares, ocupação dinâmica e a política atual de trocar de fonte quando necessário.

## Verificação após a correção

- `python -m pytest -q`: **276 passed, 1 skipped**.
- Foram adicionados testes que garantem a propagação explícita dos bloqueios dinâmicos no fluxo humano e evitam a busca estática extra quando não há bloqueios.
- Microbenchmark local de 1.000 decisões, em mundo vazio de 60×60 e primeiro alvo alcançável: padrão anterior com 2 chamadas de pathfinder por decisão, **0,421 ms/decisão**; seletor atualizado com 1 chamada, **0,197 ms/decisão**. Isso representa cerca de 53% menos tempo nesse cenário sintético, não uma previsão de ganho equivalente na auditoria completa.
- A auditoria completa de oito execuções excedeu o limite de execução deste ambiente. Ela ainda precisa ser repetida no ambiente de validação antes de considerar a correção consolidada.

A alteração não modifica limiares, prioridades cognitivas, persistência de alvos ou regras ecológicas. A migração da busca por alimento dos herbívoros permanece fora do escopo deste pacote.
