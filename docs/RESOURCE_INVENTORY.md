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
- Na primeira etapa, a política não buscava depósitos intencionalmente. A política atual acrescenta busca deliberada de madeira e pedra para construção quando não há abrigo próximo e as necessidades fisiológicas permitem.

## Geração

`SimulationConfig.wood_density` e `stone_density` determinam a quantidade de depósitos por área. Os cenários gerados preservam as posições e quantidades para uma mesma semente. A geração direta por `World` aceita `wood_count` e `stone_count`.

## Auditoria

- `ecology_history.csv`: unidades e número de depósitos restantes por material e unidades recolhidas por humanos em cada passo.
- `human_physiology_history.csv`: material coletado, peso e quantidades do inventário após cada passo.
- `humans.csv`: inventário final de cada humano.

## Limitações deliberadas

Ainda não existem ferramentas, receitas de construção, armazenamento compartilhado, troca, uso de material por animais ou política que planeje a coleta de materiais. Depósitos são recursos finitos colocados aleatoriamente; não se regeneram. A próxima evolução deve acrescentar uma mecânica material com uso concreto, não expandir as métricas ecológicas por si só.


# Incremento 2 — depósito compartilhado

- Cada cenário criado por `Scenario.to_world`, `run_single_simulation` e `main.py` possui um depósito fixo no ponto inicial.
- O depósito tem capacidade inicial de 500 unidades de peso e armazena alimento, madeira, pedra e fibra.
- Alimento agora ocupa peso 1 no inventário individual. Plantas maduras e itens `Food` são coletados para o inventário; uma porção é consumida quando a fome chega a 35.
- Ao permanecer sobre o depósito, o agente deposita materiais carregados; também deposita alimento excedente, mantendo uma porção portátil. Se estiver com fome >= 35 e sem alimento no inventário, retira uma porção do depósito.
- As transferências respeitam a capacidade de ambos os inventários e os métodos retornam as quantidades efetivamente transferidas.
- A camada de estrutura é separada da camada de recurso e não bloqueia movimento. O depósito é desenhado no mapa e seu estoque é mostrado na sidebar.
- `ecology_history.csv` registra estoque e capacidade do depósito, coleta, consumo, depósito e retirada de alimento e materiais.

Limitação desta etapa histórica: os agentes não planejavam rotas até o depósito; interagiam quando passavam por ele. As etapas posteriores acrescentaram abrigos compartilhados e construção autônoma.


# Incremento 3 — abrigo com armazenamento e construção autônoma

- `Shelter` herda a interface de `Storage`: cada abrigo pode armazenar alimento, madeira, pedra e fibra, com capacidade padrão de 500 unidades de peso.
- A estrutura de armazenamento inicial criada por `main.py`, `Scenario.to_world` e `run_single_simulation` agora é um abrigo, e não um baú separado.
- Humanos cansados procuram abrigos livres se energia estiver abaixo de 50 e fome/sede não forem urgentes. Descansam até 70 de energia.
- Quando não há abrigo a até 8 células, humanos com necessidades controladas procuram madeira e pedra. Ao carregar 5 madeiras e 2 pedras, procuram uma célula livre afastada de outros abrigos e constroem autonomamente.
- O controle manual desativa a construção autônoma para o humano controlado. Abrigos continuam caminháveis e a proteção contra predadores permanece aplicada.
- A política é baseada em regras; não há treinamento de modelo de aprendizado de máquina nesta versão.
