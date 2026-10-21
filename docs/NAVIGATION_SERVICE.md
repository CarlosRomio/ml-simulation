# Contrato compartilhado de navegação

`agents.navigation.service.NavigationService` concentra a infraestrutura mínima
que as entidades precisam para consultar rotas. Ele não decide para onde um
agente deve ir; recebe início, destino e, opcionalmente, posições bloqueadas.

## API

- `find_path(world, start, goal, blocked_positions=None)` retorna a rota incluindo
  início e destino, ou `None` se não houver rota válida.
- `next_step(path, current)` retorna o deslocamento ortogonal até a próxima célula,
  ou `None` se a rota estiver ausente, obsoleta ou concluída.

## Responsabilidades mantidas fora do serviço

- limiares fisiológicos e prioridade entre sede, fome, caça, descanso e exploração;
- seleção e persistência de alvos;
- regras de fuga e combate;
- resolução de colisões entre agentes que planejam simultaneamente;
- política de percepção e quais recursos entram na lista de candidatos.

## Migração gradual

A função `agents.navigation.bfs.find_path` permanece disponível para compatibilidade.
As políticas de cada espécie continuam separadas. O serviço é uma fronteira de
infraestrutura, não uma tentativa de forçar todas as espécies a se comportarem da
mesma maneira.
