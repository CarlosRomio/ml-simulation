# Instrumentação de progresso dos alvos

## Objetivo

Registrar a relação entre alvo selecionado, deslocamento e resultado observado sem alterar a política de decisão dos agentes.

## Campos por passo

A história de atividade passa a registrar:

- `target_intent_before_action`: intenção associada ao alvo antes da ação;
- `target_x_before_action` e `target_y_before_action`: coordenadas do alvo capturado antes do movimento;
- `target_distance_before_action` e `target_distance_after_action`: distância Manhattan ao mesmo alvo antes e depois da ação;
- `target_distance_progress`: distância anterior menos distância posterior; positivo significa aproximação, zero significa ausência de progresso em distância e negativo significa afastamento;
- `target_in_interaction_range`: alvo a distância Manhattan de até uma célula; é apenas uma medida geométrica, não prova que a interação foi válida;
- `target_reached`: agente terminou na coordenada exata do alvo;
- `need_satisfied_this_step`: a ação observada satisfez uma necessidade segundo os eventos já reconhecidos pela simulação.

## Arquivos de auditoria

- `target_progress_episodes.csv`: episódios consecutivos de alvo por indivíduo, incluindo duração, progresso, bloqueios, alcance e resultado observado.
- `target_progress_summary.csv`: agregação por espécie e intenção.
- `activity_sampled.csv` e `activity_events.csv`: incluem os campos de progresso quando a linha é amostrada ou selecionada como evento.

Um episódio termina quando o alvo é removido/limpo, muda, ou termina a observação. Para carnívoros em intenção `HUNT`, uma mudança de coordenadas é tratada como movimento da presa e não como troca automática de alvo.

## Limitações de interpretação

- Progresso em distância não prova que havia uma rota válida nem que o agente seguiu a rota planejada.
- `target_in_interaction_range` não garante que o recurso ainda exista ou que as condições da interação sejam satisfeitas.
- `target_reached` significa apenas coordenada exata. A satisfação da necessidade é registrada separadamente.
- A instrumentação é observacional e não deve modificar decisões, recompensas, percepção ou parâmetros comportamentais.
