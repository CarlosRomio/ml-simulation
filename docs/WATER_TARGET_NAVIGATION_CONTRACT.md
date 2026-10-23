# Contrato de seleção de objetivos e navegação — busca por água

## Escopo

Esta etapa integra o contrato compartilhado somente à busca por água dos herbívoros. Não altera os limiares de sede/fome, a prioridade entre necessidades, a fuga de predadores nem a navegação de alimento. Humanos e carnívoros permanecem nos fluxos anteriores.

## Responsabilidades

- `Herbivore.choose_action`: decide quando a sede justifica procurar água e mantém as prioridades comportamentais da espécie.
- `TargetSelector.select_reachable_target`: ordena os candidatos por distância Manhattan (com desempate por `y` e depois `x`), tenta os candidatos nessa ordem e retorna o primeiro resultado de navegação bem-sucedido, junto das tentativas realizadas.
- `NavigationService.plan_route`: classifica cada tentativa como `PATH_FOUND`, `ALREADY_AT_GOAL`, `INVALID_GOAL`, `TEMPORARILY_BLOCKED` ou `UNREACHABLE`, com motivo explícito quando aplicável.
- `NavigationService.next_step`: converte a rota escolhida em um deslocamento local.

## Resultado do seletor

`TargetSelectionResult` contém:

- `target`: coordenada escolhida, ou `None` se nenhum candidato for alcançável;
- `navigation`: resultado do planejamento para o candidato escolhido, ou `None` se não houver seleção;
- `attempts`: resultados das tentativas na ordem em que foram realizadas.

Cada `TargetSelectionAttempt` registra o destino, o resultado semântico do serviço, a rota estática de referência e os passos dessa rota que estavam ocupados dinamicamente. Isso preserva a observabilidade de bloqueios mesmo quando existe uma rota alternativa.

`ALREADY_AT_GOAL` é sucesso para esse fluxo: se o herbívoro já está sobre uma fonte de água, ele permanece no local para beber. A API anterior `nearest_reachable_target` permanece disponível para evitar migração ampla nesta etapa.

## Verificação

- Testes específicos cobrem destino inválido seguido de alternativa válida, bloqueio temporário e agente já no destino.
- Suíte completa: 269 passaram, 1 ignorado.
- Auditoria piloto (2 execuções, 300 passos, sementes a partir de 7200): os CSVs de eventos, decisões, acesso a recursos, população, ecologia e caça ficaram idênticos à versão anterior. Apenas os campos de duração e taxa de execução no `manifest.json` diferiram.

O piloto confirma equivalência para esse cenário curto; a aceitação final requer repetir a auditoria completa de oito execuções por 3.000 passos no ambiente de desenvolvimento.
