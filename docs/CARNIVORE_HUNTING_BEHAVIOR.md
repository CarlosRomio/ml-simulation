# Comportamento de exploração e caça dos carnívoros

## Objetivos

Esta etapa diferencia a locomoção do predador sem alterar as regras de dano,
consumo de carne, fome basal ou defesa humana.

## Exploração sem presa visível

Quando não há presa ou água acessível, o carnívoro seleciona um waypoint de
patrulha persistente, em vez de sortear uma direção nova a cada minuto. A rota
é mantida enquanto o animal avança e o waypoint é renovado ao alcançá-lo ou
quando a rota fica bloqueada.

## Perseguição

Quando há alvo distante e fome/sede urgente, o carnívoro pode executar uma
arrancada de até três células, desde que tenha a reserva de estamina exigida
pela configuração existente. A movimentação percorre os passos da rota BFS,
em vez de repetir a mesma direção, o que permite contornar obstáculos durante
a arrancada.

A arrancada custa 2 unidades de estamina por célula efetivamente percorrida
(até 6 unidades para três células). Caminhar continua custando 1 unidade por
célula. Herbívoros e humanos não tiveram sua velocidade alterada nesta etapa.

## Limitações conhecidas

- O caminho é calculado sobre o mapa estático; ocupação por outros indivíduos
  pode bloquear uma rota temporariamente.
- A escolha de waypoint não garante que o predador encontre uma presa; ela
  aumenta a cobertura espacial de exploração.
- A extinção continua possível sem reprodução e não é artificialmente evitada.
- Esta etapa deve ser avaliada com uma auditoria ecológica antes de qualquer
  ajuste adicional de fome, dano ou recompensa alimentar.
