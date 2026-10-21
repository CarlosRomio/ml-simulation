# Fisiologia temporal — etapa 2: sono, corrida e estamina

## Convenção temporal

Cada passo equivale a um minuto simulado. O relógio do mundo é independente do tempo real de execução. O experimento de calibração usa 900 passos (15 horas simuladas) por execução.

## Comportamentos

- **Esperar:** não desloca; recuperação passiva pequena de estamina; fadiga continua aumentando.
- **Caminhar:** desloca uma célula por passo; custo de estamina por célula; fadiga aumenta moderadamente.
- **Correr:** desloca até duas células por passo; custa 8 pontos de estamina e acumula fadiga mais rapidamente. O deslocamento real pode ser menor quando há obstáculos, limites do mapa ou outras entidades.
- **Descansar:** permanece parado e recupera estamina. Abrigos melhoram a recuperação de estamina.
- **Dormir:** estado persistente que reduz fadiga por minuto. O sono termina quando a fadiga chega a 15 ou é interrompido por fome, sede ou predador próximo.

A corrida autônoma é usada em perseguições e quando necessidades urgentes tornam justificável chegar mais rapidamente a um recurso. No controle manual, segure Shift junto com WASD/setas para solicitar corrida. A corrida manual também exige reserva mínima de estamina.

A estamina também limita ataques: humanos e carnívoros precisam de pelo menos 8 pontos para atacar e gastam 8 por ataque. Estamina zero não causa morte diretamente; impede corrida e ataques até haver recuperação.

## Parâmetros atuais

Os valores estão em `configuration/physiology_config.py` e são parâmetros abstratos, não estimativas médicas:

| Parâmetro | Valor inicial |
|---|---:|
| Início do sono | Fadiga 65/100 |
| Fim normal do sono | Fadiga 15/100 |
| Recuperação de fadiga dormindo | 0,15 por minuto |
| Recuperação de fadiga dormindo em abrigo | 0,18 por minuto |
| Fadiga por minuto caminhando | +0,15 |
| Fadiga por minuto correndo | +0,45 |
| Custo de corrida | 8 estamina por passo de corrida |
| Recuperação de estamina em descanso comum | +2 por minuto |
| Recuperação de estamina em abrigo | +8 por minuto |

O sono só começa quando fome e sede não exigem prioridade imediata. Durante o sono, a fome pode ser atendida automaticamente se o humano tiver alimento no inventário. Sem alimento, o sono é interrompido quando a fome chega a 35; sede interrompe em 40. Um predador a até quatro células interrompe o sono.

## Experimento inicial de calibração

Comando:

```powershell
py -3.13 run_physiology_experiment.py
```

Configuração: 8 sementes reproduzíveis, 900 passos por execução, 4 humanos, 8 herbívoros e 2 carnívoros em mundo de 30×30. A execução gera:

- `results/physiology_calibration/runs.csv`: resumo por execução e sobrevivência;
- `results/physiology_calibration/activity_history.csv`: atividade, decisão, movimento, estamina gasta/recuperada, custos metabólicos, fadiga, fome, sede, saúde e interrupções do sono por indivíduo e passo;
- `results/physiology_calibration/activity_summary.csv`: médias agregadas por espécie e atividade.

### Resultado observado na execução registrada

- Sobrevivência humana: 21 de 32 (65,6%).
- Mortes humanas por predação: 11.
- Mortes humanas por fome: 0.
- Mortes humanas por sede: 0.
- Mortes de herbívoros: 14 por caça humana, 2 por predação, 4 com componente de fome e 3 com componente de sede.
- Mortes de carnívoros: 4 por defesa humana, 11 com componente de fome e 2 com componente de sede.
- Uma morte pode ter fome e sede registradas no mesmo passo; por isso, as contagens fisiológicas se sobrepõem e não devem ser somadas como causas exclusivas.
- Linhas de auditoria fisiológica: 70.524, incluindo eventos de morte registrados antes da vez normal do animal.
- Passos em sono: 13.595; passos em corrida: 555; passos em descanso: 8.667.
- Distância média por corrida bem-sucedida: humanos 1,97 células; herbívoros 1,93; carnívoros 1,94.
- Custo de estamina por corrida bem-sucedida: 8 pontos para as três categorias.
- Variação média de fadiga por atividade: espera +0,10; caminhada +0,15; corrida +0,45; descanso +0,02; sono −0,15 por minuto.

Esses resultados mostram que os mecanismos estão sendo exercitados e que, nesse lote, não houve morte humana por fome ou sede. Não demonstram ainda que os parâmetros estejam calibrados: oito sementes são uma amostra inicial, e a principal causa de morte humana foi predação. Carnívoros tiveram poucos ou nenhum episódio de sono no lote porque a prioridade de caça frequentemente impediu que atingissem as condições de repouso. Isso merece uma análise própria antes de alterar taxas fisiológicas.

## Interpretação e próximo ajuste

Os CSVs devem ser lidos separando custos de movimento, custos de combate, recuperação de estamina e variação líquida de fome/sede. A variação líquida de fome pode ser negativa durante um passo por causa da alimentação; os campos `hunger_metabolic_cost` e `thirst_metabolic_cost` registram separadamente os custos metabólicos brutos daquele passo.

Não ajustar os parâmetros apenas para aumentar sobrevivência. Primeiro verificar se a atividade escolhida, o custo correspondente e a recuperação registrada concordam com as regras. Depois executar um lote maior com sementes pareadas e comparar distribuições de sobrevivência, fadiga, estamina e duração dos episódios de sono.
