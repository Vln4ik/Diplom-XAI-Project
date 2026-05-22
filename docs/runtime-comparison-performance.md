# Сравнение runtime-профилей: fallback vs Ollama (performance)

Дата фиксации: `2026-05-22 (Europe/Moscow)`

## Сценарий

- profile: `performance`
- fallback runtime: `hash-fallback + template-fallback`
- ollama runtime: `ollama + all-minilm + gemma3:270m`
- fallback providers: embeddings `hash-fallback`, llm `template-fallback`
- ollama providers: embeddings `ollama (all-minilm)`, llm `ollama (gemma3:270m)`
- raw fallback artifact: [runtime-comparison-performance-fallback.json](runtime-comparison-performance-fallback.json)
- raw ollama artifact: [runtime-comparison-performance-ollama.json](runtime-comparison-performance-ollama.json)

## Ключевые метрики

| Метрика | Fallback | Ollama | Delta | Delta % |
|---|---:|---:|---:|---:|
| `total_wall_time_seconds` | `12.7880` | `17.9265` | `+5.1385` | `+40.18%` |
| `throughput_runs_per_minute` | `9.3838` | `6.6940` | `-2.6898` | `-28.66%` |

## Сравнение по этапам

| Этап | Fallback mean, s | Ollama mean, s | Delta, s | Delta % |
|---|---:|---:|---:|---:|
| `analyze` | `1.0198` | `1.0185` | `-0.0013` | `-0.13%` |
| `create_organization` | `0.0077` | `0.0066` | `-0.0011` | `-14.29%` |
| `create_report` | `0.0095` | `0.0109` | `+0.0014` | `+14.74%` |
| `export_docx` | `0.0289` | `0.0321` | `+0.0032` | `+11.07%` |
| `export_explanations` | `0.0042` | `0.0044` | `+0.0002` | `+4.76%` |
| `export_matrix` | `0.0092` | `0.0095` | `+0.0003` | `+3.26%` |
| `export_package` | `0.0263` | `0.0262` | `-0.0001` | `-0.38%` |
| `fetch_matrix` | `0.0144` | `0.0107` | `-0.0037` | `-25.69%` |
| `fetch_requirements` | `0.0100` | `0.0082` | `-0.0018` | `-18.00%` |
| `generate` | `1.0150` | `3.5539` | `+2.5389` | `+250.14%` |
| `login` | `0.0580` | `0.0541` | `-0.0039` | `-6.72%` |
| `process_education_metrics.csv` | `1.0215` | `1.0234` | `+0.0019` | `+0.19%` |
| `process_organization_profile.json` | `1.0211` | `1.0208` | `-0.0003` | `-0.03%` |
| `process_rosobrnadzor_evidence_site.txt` | `1.0217` | `1.0217` | `+0.0000` | `+0.00%` |
| `process_rosobrnadzor_sample.txt` | `1.0187` | `1.0199` | `+0.0012` | `+0.12%` |
| `process_total` | `4.1297` | `4.1285` | `-0.0012` | `-0.03%` |
| `search` | `0.0175` | `0.0544` | `+0.0369` | `+210.86%` |
| `upload_education_metrics.csv` | `0.0083` | `0.0033` | `-0.0050` | `-60.24%` |
| `upload_organization_profile.json` | `0.0033` | `0.0034` | `+0.0001` | `+3.03%` |
| `upload_rosobrnadzor_evidence_site.txt` | `0.0039` | `0.0038` | `-0.0001` | `-2.56%` |
| `upload_rosobrnadzor_sample.txt` | `0.0066` | `0.0060` | `-0.0006` | `-9.09%` |
| `upload_total` | `0.0227` | `0.0171` | `-0.0056` | `-24.67%` |

## Интерпретация

- Это сравнение показывает именно runtime-стоимость локальной модели, а не формальную semantic-оценку качества текста.
- `fallback` режим опирается на `hash-fallback` embeddings и `template-fallback` generation, поэтому служит нижней границей по latency.
- `Ollama` режим нужен не ради скорости, а ради более естественной генерации narrative sections при сохранении evidence-grounded pipeline.
- Наибольшая разница сосредоточена в `generate`: mean `1.0150s` -> `3.5539s` (+250.14%).
- Доменные этапы `process_total` и `analyze` меняются умеренно: `4.1297s` -> `4.1285s` и `1.0198s` -> `1.0185s`.
- Throughput меняется с `9.3838` до `6.6940` runs/min (-28.66%).
- Если различия по `process_total` и `analyze` малы, значит bottleneck сосредоточен в генеративном слое, а не в основном document/retrieval/XAI pipeline.

