# Atualização: estamina antecipatória, persistência de caça e cobertura espacial

## Decisões implementadas

- A política de descanso considera o custo estimado da próxima arrancada e preserva uma reserva de 30% da capacidade individual após o esforço previsto.
- A decisão de descansar dos humanos é avaliada mesmo quando a estamina está abaixo do mínimo necessário para correr.
- Caçar deixou de ser classificado automaticamente como emergência para a corrida humana; a corrida de caça usa os limiares normais, salvo necessidade fisiológica crítica.
- Herbívoros preservam a prioridade de fuga, mas necessidades apenas elevadas não liberam automaticamente a reserva de corrida.
- Carnívoros podem recuperar antes de iniciar uma perseguição, com uma reserva calculada a partir do custo de deslocamento e da capacidade individual.
- A identidade da presa atual é preservada entre passos. O alvo é trocado se desaparecer, morrer, sair da visão ou uma alternativa estiver materialmente mais próxima.
- A auditoria gera `spatial_coverage_summary.csv`, com células únicas visitadas, revisitas, cobertura do mundo, distância percorrida e distribuição de atividades por indivíduo.
- Episódios de caça da auditoria usam a identidade da presa quando disponível, em vez de tratar todo movimento do alvo como um único episódio indiferenciado.

## Validação

Executar `python -m pytest -q` e uma auditoria curta com `--profile pilot --runs 2 --steps 100 --workers 2`. A cobertura espacial é calculada a partir do histórico completo por indivíduo, não apenas da amostra periódica.

Os parâmetros continuam sendo hipóteses de modelagem; comparar réplicas longas é necessário para concluir se melhoram sobrevivência, eficiência de caça ou exploração.
