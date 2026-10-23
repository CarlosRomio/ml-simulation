# Perfis de fome e preparação para reprodução

## Objetivo

Reduzir a pressão constante de busca por alimento para que os agentes tenham janelas maiores para exploração e, quando o ciclo reprodutivo estiver implementado, busca por parceiros. A mudança é fisiológica e não altera diretamente a política de seleção de alvos.

## Taxas basais por minuto simulado

As taxas ficam centralizadas em `configuration/species_physiology.py`:

| Espécie | Taxa basal anterior | Nova taxa basal de referência |
|---|---:|---:|
| Humanos | 0,25 | 0,18 |
| Herbívoros | 0,30 | 0,18 |
| Carnívoros | 0,30 | 0,10 |

Os custos adicionais de fome por movimento também foram reduzidos em `configuration/physiology_config.py`:

- Caminhada: `0.01` → `0.005` por passo.
- Corrida: `0.05` → `0.025` por passo.

Os custos de sede não foram alterados.

## Relação com a genética

`adjusted_hunger_rate()` aplica o atributo hereditário `metabolic_efficiency` tanto à taxa basal configurada para o indivíduo quanto ao custo adicional de fome da atividade. Valores de eficiência acima da média da espécie reduzem o consumo; valores abaixo da média aumentam o consumo. O multiplicador permanece limitado pela implementação existente de `IndividualAttributes.relative_multiplier()`.

A taxa da configuração humana continua sendo uma taxa de referência: se o usuário fornecer `SimulationConfig.hunger_per_step`, o valor customizado será ajustado pela eficiência metabólica de cada indivíduo.

## Limites desta etapa

Esta alteração aumenta as janelas de exploração, mas **não implementa ainda a busca por parceiros**. No código atual, os indivíduos ainda não possuem um ciclo de vida reprodutivo completo com idade, maturidade sexual, elegibilidade, pareamento, gestação/incubação e nascimento. Marcar exploração genérica como `SEEK_MATE` antes desses contratos existirem produziria telemetria enganosa.

A próxima etapa deve implementar esses contratos por espécie e só então introduzir a busca por parceiro como um objetivo comportamental de prioridade intermediária, subordinado a necessidades críticas como sobrevivência imediata, hidratação e fome extrema.

## Validação

- Testes automatizados: `302 passed, 1 skipped`.
- Auditoria de integração curta: 1 execução, 100 passos, mundo 60×60, concluída com exportação dos CSVs esperados.
- A auditoria longa de 4 execuções × 1.000 passos excedeu o limite de tempo do ambiente de desenvolvimento e não foi usada como evidência ecológica.
