# Auditoria do ecossistema

## Objetivo

A auditoria separa a variação entre sementes dos comportamentos sistemáticos, registra o estado inicial de cada indivíduo e produz resumos usando todos os registros, sem exigir a exportação de cada observação individual de cada minuto.

## Execução

### Piloto (recomendado primeiro)

```powershell
py -3.13 run_ecosystem_audit.py --profile pilot --workers 4
```

Configuração: 4 execuções, mundo 30×30, 4 humanos, 8 herbívoros, 2 carnívoros, 600 passos (10 horas simuladas por execução). Serve para confirmar o ambiente e a instrumentação.

### Auditoria completa

```powershell
py -3.13 run_ecosystem_audit.py --profile full --workers 4
```

Configuração: 30 execuções com sementes independentes, mundo 60×60, 20 humanos, 40 herbívoros, 8 carnívoros, 3.000 passos (50 horas simuladas por execução). O processo usa quatro workers por padrão; aumente apenas se houver memória disponível.

### Teste de escala com menos dados brutos

```powershell
py -3.13 run_ecosystem_audit.py --profile full --runs 8 --steps 1200 --workers 4 --sample-every 20 --output results/ecosystem_audit_scale_test
```

Os resumos e os históricos agregados usam todos os passos. `activity_sampled.csv` guarda uma observação periódica por indivíduo e `activity_events.csv` preserva mudanças de atividade, danos, interrupções do sono, necessidades críticas, baixa estamina e mortes.

## Saídas

- `manifest.json`: parâmetros, sementes, duração, paralelismo e tempo computacional.
- `runs.csv`: uma linha por execução, sobrevivência e causas de morte por espécie, ataques, coleta de alimento e tempo de execução.
- `initial_states.csv`: estado fisiológico inicial de cada indivíduo.
- `activity_summary.csv`: distribuição de atividades e médias/custos agregados usando todos os registros.
- `action_reason_summary.csv`: frequência das razões de ação por espécie, atividade e intenção.
- `activity_sampled.csv`: histórico individual amostrado, incluindo intenção, ação cognitiva e rastreamento de alternativas quando disponível.
- `activity_events.csv`: observações relevantes em resolução completa.
- `population_history.csv`: métricas populacionais por passo.
- `ecology_history.csv`: dinâmica de recursos e interações ecológicas por passo.
- `social_decisions.csv`: decisões sociais registradas pelo sistema atual.
- `carnivore_hunt_history.csv`: uma linha por carnívoro ativo e passo, com presas disponíveis/visíveis, distância até a presa mais próxima e água, alvo escolhido, movimento, oportunidade de ataque, motivo de ataque não realizado, dano causado/recebido, abate, redução efetiva da fome e estado fisiológico final do passo.
- `carnivore_hunt_summary.csv`: resumo por execução e carnívoro, incluindo passos com fome crítica, passos sem presas visíveis, passos com estamina baixa, ataques, abates, dano recebido por defesa e estado/causa no encerramento.

## Critérios de leitura

1. Não avaliar a simulação apenas pela média de sobrevivência; verificar dispersão entre sementes e causas de morte.
2. Comparar fome/sede críticas com ações tomadas nos passos anteriores, e não apenas com o estado final.
3. Verificar se descanso/sono recuperam estamina/fadiga conforme os parâmetros e se as interrupções têm uma causa registrada.
4. Comparar distância percorrida, gasto de estamina e atividade. Corrida deve ter distância maior que caminhada e custo consistente com a regra configurada.
5. Separar mortes por caça, predação, defesa, fome e sede. Uma execução com extinção de uma espécie não basta para concluir que o modelo está sistematicamente desequilibrado.
6. `activity_sampled.csv` é amostrado; usar `activity_summary.csv`, `action_reason_summary.csv`, `activity_events.csv` e `population_history.csv` para conclusões quantitativas.
7. O relógio simulado equivale a um minuto por passo; a velocidade computacional não altera o tempo simulado.
8. Para diagnosticar morte por fome de carnívoros, comece por `carnivore_hunt_summary.csv` e depois siga o indivíduo no `carnivore_hunt_history.csv`. Verifique se a fome ficou crítica, se havia presas visíveis, se a estamina estava abaixo do custo de ataque (8), se o ataque foi tentado e se houve abate/recuperação de fome.
9. Os campos adicionais são observacionais: não mudam a seleção de ações, o combate, o metabolismo nem os parâmetros do modelo.

## Nota de performance

Cada réplica é executada em um processo independente. O worker grava os históricos em arquivos temporários locais e retorna apenas estatísticas compactas, evitando transferir todos os dicionários de observação entre processos. Os arquivos temporários são removidos após a consolidação.
