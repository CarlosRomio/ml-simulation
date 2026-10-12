# ML Simulation — auditoria fisiológica e ecológica

Projeto de simulação em grade para estudar sobrevivência de humanos e interações com herbívoros e carnívoros. Nesta etapa, os agentes usam regras explícitas; não há aprendizado de máquina treinado.

## Executar

```powershell
py -3.13 -m pytest -q
py -3.13 run_ecosystem_experiment.py
```

O experimento ecológico usa 20 sementes reproduzíveis, 300 passos por execução e as configurações declaradas em `run_ecosystem_experiment.py`. Os CSVs são gerados em `results/ecosystem_experiment/`:

- `runs.csv`: uma linha por execução, com mortalidade, necessidades, alimentação, ataques e estado final das populações.
- `humans.csv`: uma linha por humano, incluindo métricas individuais e causa de encerramento.
- `population_history.csv`: uma linha por passo e execução, com população e médias fisiológicas.
- `human_physiology_history.csv`: uma linha por humano e passo, com posição, ação, estado fisiológico antes/depois, gasto/recuperação de estamina e dano por causa.

## Comparação controlada da regeneração

Para medir o efeito da regeneração sem alterar a política dos agentes, execute:

```powershell
py -3.13 run_regeneration_comparison.py
```

O experimento compara 0, 1 e 2 sementes solicitadas por atualização, com 20 execuções pareadas por tratamento e 300 passos. Cada tratamento começa com 54 plantas maduras, 18 itens de alimento estático, 18 fontes de água, 9 obstáculos e 5 humanos, 8 herbívoros e 3 carnívoros. Apenas `seed_spawn_count` muda entre tratamentos. Usa até quatro processos. Os CSVs são gravados em `results/regeneration_comparison/`. Consulte `docs/REGENERATION_COMPARISON.md` para o desenho experimental, a semântica das métricas e as limitações conhecidas.

## Convenções fisiológicas

Os números são **unidades abstratas do simulador**, não medidas fisiológicas reais.

- **Saúde (`health`)**: condição física. Chegar a zero significa morte.
- **Energia (`energy`)**: estamina para movimentação e ações exigentes. Chegar a zero não mata; impede corrida por falta de estamina e pode ser recuperada ao descansar ou comer.
- **Fome (`hunger`)** e **sede (`thirst`)**: escalas de necessidade em que zero representa necessidade satisfeita e o limite máximo representa necessidade extrema.
- Fome e sede aumentam por passo. Ao alcançar seus limiares críticos, aplicam dano à saúde a cada passo enquanto permanecerem críticas, salvo se o dano configurado for zero.
- Uma causa de dano só é contabilizada quando reduz efetivamente a saúde. Se fome e sede causarem dano no mesmo passo, ambas ficam registradas; se a primeira já zerar a saúde, a segunda não é contabilizada como dano efetivo.
- A causa da morte é determinada pelo dano efetivo, nunca por estamina zero. `STARVATION_AND_DEHYDRATION` significa que ambos os mecanismos causaram dano efetivo no passo letal.
- Médias `*_mean_*` em `population_history.csv` descrevem os indivíduos **vivos**. Colunas `*_all_mean_*` descrevem toda a coorte, incluindo indivíduos mortos, cujas necessidades ficam no estado em que estavam quando morreram.
- `water_units_consumed` é compatibilidade histórica: registra a redução efetiva da sede atribuível à água, não uma medida física independente de volume.

## Regras de interpretação

1. Uma execução reproduzível não prova, por si só, que a regra ecológica esteja correta; testes controlados validam regras específicas.
2. Sobrevivência, mortalidade por causa, níveis fisiológicos, recursos e comportamento devem ser lidos em conjunto.
3. Ao comparar versões, mantenha configuração, número de passos e sementes iguais. Alterações nas regras de movimento/estamina mudam os resultados e devem ser tratadas como mudança de modelo, não como simples correção de relatório.
4. `ExperimentSummary.starvation_runs` é mantido por compatibilidade e historicamente representa execuções sem sobreviventes; o nome correto dessa métrica é `extinction_runs`. Mortes individuais por fome ficam em `average_deaths_by_starvation`.

## Testes

A suíte cobre as necessidades, limites fisiológicos, causas de dano, consumo/recuperação de estamina, métricas agregadas, histórico individual e exportação CSV. Ao introduzir uma nova mecânica, adicione primeiro testes unitários e um cenário de experimento controlado antes de alterar parâmetros globais.


## Recursos materiais e inventário

O mundo agora pode conter depósitos coletáveis de madeira e pedra. Cada depósito tem uma quantidade variável, pode ser recolhido parcialmente e permanece na célula até acabar. Humanos têm inventário com capacidade limitada por peso: madeira pesa 1 unidade por item, pedra pesa 2 e fibra (reservada para extensões futuras) pesa 0,5. A coleta de material não é tratada como alimentação nem altera diretamente fome/energia. A política humana atual não procura materiais deliberadamente; ela os coleta ao passar por um depósito, permitindo validar a mecânica sem alterar a política de sobrevivência nesta etapa.

Densidades configuráveis: `wood_density` e `stone_density` em `SimulationConfig`. O histórico `human_physiology_history.csv` registra o inventário por passo; `humans.csv` inclui o inventário final de cada indivíduo; `ecology_history.csv` registra o estoque no mundo e as unidades coletadas.

Consulte `docs/RESOURCE_INVENTORY.md` para as regras e os limites atuais.

## Interface visual

A barra lateral foi reorganizada em seções: mundo, vegetação, materiais, agente observado e interações. O conteúdo central é rolável pela roda do mouse quando não cabe na altura disponível; o cabeçalho e os controles permanecem fixos. A roda do mouse sobre o mapa continua controlando o zoom.

A barra lateral mostra as quantidades do inventário do humano selecionado. Para selecionar outro humano, clique nele no mapa.

### Correção de renderização da barra lateral

A chamada de desenho das barras fisiológicas passa explicitamente a cor e a coordenada vertical ao renderizador. Foi adicionado um teste de regressão que desenha a barra lateral completa, incluindo estamina, fome e sede, para detectar incompatibilidades na assinatura de `_draw_bar`.
