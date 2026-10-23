# Calibração de fadiga dos carnívoros

## Motivação

O perfil geral acumulava fadiga a +0,15/min caminhando e +0,45/min correndo, mas recuperava apenas 0,15/min durante o sono e continuava acumulando 0,02/min durante o descanso. Para carnívoros que percorrem distâncias maiores por passo e precisam alternar exploração, perseguição e recuperação, isso criava uma assimetria: uma sessão de corrida podia exigir muito tempo de recuperação, e o descanso comum não removia fadiga.

## Perfil inicial proposto

| Atividade | Variação de fadiga por minuto |
|---|---:|
| Espera | +0,05 |
| Caminhada | +0,10 |
| Corrida | +0,30 |
| Descanso | −0,12 |
| Sono | −0,45 |
| Sono em abrigo | −0,55 |

Os valores são parâmetros abstratos de simulação e se aplicam apenas aos carnívoros. Humanos e herbívoros mantêm o perfil anterior.

## Interpretação

- Descansar passa a recuperar fadiga, em vez de aumentá-la.
- Dormir recupera fadiga três vezes mais rápido que o perfil geral anterior.
- A corrida continua acumulando mais fadiga que a caminhada, mas a taxa é reduzida para não penalizar excessivamente deslocamentos longos.
- Os limiares de início/fim do sono e os custos de estamina não foram alterados nesta mudança; são dimensões separadas e devem ser calibradas com dados próprios.

## Validação necessária

Executar testes e auditorias com sementes pareadas, comparando mortalidade por defesa/fome/sede, fadiga média, tempo em sono/descanso/corrida, presas abatidas e cobertura espacial. A mudança deve ser considerada uma hipótese de calibração, não um equilíbrio ecológico já demonstrado.
