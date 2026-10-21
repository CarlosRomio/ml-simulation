# Linha de base: busca por água por espécie

Este documento acompanha `tests/test_water_search_characterization.py`. Os testes são de caracterização: registram as diferenças da implementação atual para tornar explícitas as mudanças futuras. Não afirmam que as políticas atuais são ideais.

## Política atual observada no código

| Dimensão | Humano (`Agent`) | Herbívoro (`Herbivore`) | Carnívoro (`Carnivore`) |
|---|---|---|---|
| Gatilho de busca por água | Candidato cognitivo elegível a partir de sede `>= 12` | Busca por água a partir de sede `>= 45` | Prioridade sobre caça a partir de sede `>= 50`; fallback a partir de `>= 35` quando não selecionou presa |
| Seleção de alvo | Menor caminho alcançável; água compete com alimento, descanso, sono, espera e exploração | Fontes ordenadas por distância Manhattan e avaliadas em ordem; procura alternativa se fonte estiver bloqueada/inacessível | Fontes ordenadas por distância Manhattan; água e presas participam de uma prioridade sequencial |
| Navegação | BFS; na simulação, pode evitar posições ocupadas | BFS com bloqueios dinâmicos fornecidos pelo chamador | BFS estático, sem o mesmo argumento de bloqueios dinâmicos |
| Persistência | Alvo pode persistir; reavaliação periódica a cada cinco decisões para objetivos de água/alimento | Seleção reexecutada a cada chamada; alvo pode mudar se a lista de candidatos ou ocupação mudar | Seleção reexecutada a cada chamada; o alvo pode mudar quando a prioridade ou os candidatos mudam |
| Conclusão local | Se já estiver sobre água e sede `>= 1`, escolhe ficar parado para beber | Se a rota tem comprimento 1, escolhe ficar parado para beber | Se já estiver sobre água e sede `>= 1`, escolhe ficar parado para beber |

## Semântica de percepção

`Perception.observe()` usa distância euclidiana (círculo) com linha de visão. `World.get_nearby_cells()` usa uma janela quadrada com linha de visão. A simulação também contém consultas Manhattan diretas para vizinhos e ameaças. Isso é uma diferença de contrato que deve ser resolvida explicitamente em uma etapa própria; estes testes apenas registram a diferença atual.

## O que ainda não está padronizado

- Contrato comum para objetivo de recurso, validade do alvo e motivo de abandono.
- Política explícita de persistência/histerese para impedir alternância desnecessária entre fontes.
- Contrato comum de planejamento que permita fornecer bloqueios dinâmicos a todas as espécies.
- Eventos de ciclo de vida de busca que distingam decisão, deslocamento, chegada, consumo e cancelamento.

## Estratégia de refatoração

1. Manter estes testes enquanto se extraem contratos comuns.
2. Separar a política de seleção da execução do movimento.
3. Reutilizar o mesmo serviço de navegação, deixando cada espécie fornecer restrições e política de abandono.
4. Comparar testes, auditorias com sementes fixas e desempenho antes/depois de cada mudança.
5. Alterar estes testes apenas quando a mudança comportamental for intencional e documentada.

## Validação desta linha de base

- `tests/test_water_search_characterization.py`: 9 testes de caracterização passaram.
- Suíte completa: 250 passaram, 1 ignorado.
- Auditoria de fumaça: 2 execuções de 100 passos concluídas e CSVs gerados.
- A auditoria curta serve apenas para confirmar que o runner continua funcional; ela não é usada para inferir sobrevivência ou estabilidade ecológica.

Nenhuma regra de comportamento foi alterada nesta etapa. A próxima mudança poderá extrair um contrato comum de objetivo e navegação, mantendo as políticas por espécie e atualizando explicitamente os testes quando uma diferença comportamental for intencional.
