# Integração do contrato na busca por água dos humanos

A busca por água dos humanos agora usa `TargetSelector.select_reachable_target()` e `NavigationService` para escolher uma fonte com rota válida. A política cognitiva permanece responsável por decidir quando `SEEK_WATER` é elegível e por comparar essa ação com alimento, repouso, sono e exploração.

A integração mantém a exclusão da posição atual da lista de destinos móveis, a ordenação existente dos candidatos, a distância calculada pela rota e os metadados usados pela decisão cognitiva. O fluxo de herbívoros e as prioridades dos carnívoros não foram alterados nesta etapa.

## Validação

A mudança deve ser aceita somente após a suíte completa e uma auditoria de oito execuções com sementes 7200–7207. Comparar os CSVs com `ecosystem_audit_water_target_contract`; diferenças nos dados simulados exigem investigação antes de consolidar a refatoração.
