# Recursos materiais e inventário — incremento 1

## Objetivo

Adicionar recursos não alimentares ao mundo e uma capacidade individual de transportá-los, sem introduzir ainda construção, compartilhamento ou novas políticas de sobrevivência.

## Recursos

- `MaterialKind.WOOD`: madeira, peso 1 por unidade.
- `MaterialKind.STONE`: pedra, peso 2 por unidade.
- `MaterialKind.FIBER`: fibra, peso 0,5 por unidade; tipo preparado para uso futuro, não gerado automaticamente nesta etapa.
- Cada depósito gerado contém de 2 a 5 unidades e é coletado parcialmente.
- Depósitos são caminháveis. O agente pode permanecer sobre um depósito para recolher unidades sucessivas.

## Inventário

- Cada humano começa com inventário vazio e capacidade de peso 20.
- `Inventory.add`, `remove`, `quantity_of`, `current_weight` e `available_weight` oferecem operações explícitas.
- O limite é aplicado por peso; não é possível coletar material que não caiba.
- A coleta não transforma madeira/pedra em alimento e não reduz fome.
- A política atual não busca depósitos intencionalmente: recolhe materiais ao encontrá-los durante a exploração. Isso isola a mecânica de coleta da decisão estratégica.

## Geração

`SimulationConfig.wood_density` e `stone_density` determinam a quantidade de depósitos por área. Os cenários gerados preservam as posições e quantidades para uma mesma semente. A geração direta por `World` aceita `wood_count` e `stone_count`.

## Auditoria

- `ecology_history.csv`: unidades e número de depósitos restantes por material e unidades recolhidas por humanos em cada passo.
- `human_physiology_history.csv`: material coletado, peso e quantidades do inventário após cada passo.
- `humans.csv`: inventário final de cada humano.

## Limitações deliberadas

Ainda não existem ferramentas, receitas de construção, armazenamento compartilhado, troca, uso de material por animais ou política que planeje a coleta de materiais. Depósitos são recursos finitos colocados aleatoriamente; não se regeneram. A próxima evolução deve acrescentar uma mecânica material com uso concreto, não expandir as métricas ecológicas por si só.
