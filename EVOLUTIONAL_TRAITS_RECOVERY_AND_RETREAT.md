# Revisão evolutiva: traços, recuperação e fuga

## Mudanças

- A personalidade agora é herdada: cada traço do descendente parte da média dos pais e pode sofrer mutação gaussiana pequena, limitada a `[0, 1]`. Os atributos fisiológicos continuam usando `IndividualGenotype.inherit`.
- O parceiro reprodutivo registra uma cópia imutável da personalidade junto ao genótipo durante a gestação; a morte ou mudança posterior do parceiro não altera o material herdado.
- Descendentes de humanos, herbívoros e carnívoros recebem o perfil herdado. Eventos `BIRTH` exportam genes e traços de personalidade para permitir análises de hereditariedade.
- `AgentNeeds.restore_health` implementa cura limitada ao máximo. A simulação aplica recuperação lenta durante descanso/sono, somente quando fome e sede não estão críticas e o passo não registrou dano fisiológico. A taxa dos carnívoros é ligeiramente maior, e a constituição influencia a taxa.
- A fuga dos carnívoros considera saúde relativa, aversão a risco, agressividade, persistência, fome e superioridade numérica humana. Isso cria limiares diferentes entre indivíduos, sem tornar a fuga automática em todos os encontros.
- Quando a seleção de presa não encontra alvo seguro, o caminho normal do carnívoro recebe uma lista de alvos de caça vazia e pode seguir a rotina de exploração persistente. A exploração usa o mecanismo existente de waypoints e visitas, sem introduzir uma segunda política concorrente.
- A reconciliação de mortes compara abates do histórico de caça com mortes terminais por predação, além de conferir separadamente humanos e herbívoros. `carnivore_kill_accounting_valid` é `1` apenas quando todas as diferenças são zero.

## Parâmetros e interpretação

Os valores são parâmetros abstratos do modelo, não estimativas biológicas. A recuperação de saúde não ocorre durante perseguição ou combate, nem quando há fome/sede críticas ou dano fisiológico no mesmo passo. Personalidade afeta decisões, mas não substitui restrições físicas.

Este modelo ainda é uma aproximação de seleção natural: a sobrevivência e a reprodução condicionam a transmissão de traços, mas não há alegação de equivalência quantitativa com uma população biológica real. A validação deve observar várias gerações, variação dos traços e consequências por espécie, não apenas longevidade de carnívoros.

## Validação realizada

- Suíte completa após as alterações finais: `338 passed, 2 skipped`.
- Testes direcionados de caça/reconciliação: `7 passed`.
- Auditoria curta de fumaça: 2 execuções, 100 passos, sementes 7200–7201, mundo 25×25, 3 humanos, 8 herbívoros e 2 carnívoros; tempo computacional reportado de 1,64 s. Ambas as execuções tiveram todos os deltas de reconciliação iguais a zero.

A suíte longa de 10 execuções × 3000 passos não foi repetida.
