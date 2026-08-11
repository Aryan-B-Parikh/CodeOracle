# 3. Data Model / Schema

## Naming conventions (fixed — do not change)

- **Tables:** `snake_case`, plural (`repositories`, `functions`).
- **Columns:** `snake_case`.
- **Primary keys:** `id UUID PRIMARY KEY DEFAULT gen_random_uuid()`.
- **Foreign keys:** `<entity>_id` (e.g. `repository_id`).
- **Timestamps:** `created_at`, `updated_at` (`TIMESTAMPTZ`, `NOT NULL`).
- **API routes:** `/api/v1/<resource>`, kebab-case path segments.
- **JSON keys:** `camelCase` in request/response bodies (frontend convention).
- **Enum values:** `UPPER_SNAKE_CASE` stored as text with DB check constraints.

## Entities & relationships

```
Repository 1───N File 1───N Entity (function/class)
     │              │
     │              ├──N Call 1──1 Entity (callee)
     │              └──N Import (module-level)
     │
Repository 1───N Analysis
Repository 1───N TestRun 1──N TestCase
Repository 1───N RefactorProposal
Analysis  1───N Embedding (entity_id → chunk)
```

## Tables

### `repositories`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| name | TEXT NOT NULL | |
| source_type | TEXT | `zip` \| `github` |
| github_url | TEXT NULL | |
| languages | JSONB | `{"python": true, "java": true}` — supported booleans; `other` when unsupported/unknown files present |
| language_counts | JSONB | per-language file counts incl. known-unsupported (`{"python": 8, "JavaScript": 2, "C++": 1, "other": 1}`); `other` = unrecognized extensions |
| loc | INTEGER | total lines of code |
| entity_count | INTEGER | cached count |
| status | TEXT | `uploaded` \| `scanning` \| `parsing` \| `analyzed` \| `failed` |
| created_at / updated_at | TIMESTAMPTZ | |

### `files`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| repository_id | FK | |
| path | TEXT NOT NULL | relative repo path |
| language | TEXT | `python` \| `java` \| `other` |
| loc | INTEGER | |
| sha256 | TEXT | dedupe/uniqueness |

### `entities` (functions & classes — one table)
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| repository_id | FK | |
| file_id | FK | |
| name | TEXT NOT NULL | |
| type | TEXT | `function` \| `method` \| `class` |
| parent_id | FK NULL | enclosing class (methods) |
| signature | TEXT | raw signature |
| language | TEXT | |
| line_start / line_end | INTEGER | citeable evidence range |
| complexity | INTEGER | Radon CCN / cyclomatic |
| is_public | BOOLEAN | |
| docstring | TEXT NULL | existing docs |
| metadata | JSONB | args, return type, decorators, globals touched |

Indexes: `(repository_id, name)`, `(file_id)`.

### `calls` (edges — function → function)
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| repository_id | FK | |
| caller_id | FK → entities | |
| callee_id | FK → entities | |
| call_line | INTEGER | evidence |
| external | BOOLEAN | callee not in repo (stdlib/third-party) |

### `imports`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| file_id | FK | |
| module | TEXT | imported module name |
| local_name | TEXT NULL | alias |
| is_external | BOOLEAN | |

### `analyses`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| repository_id | FK | |
| status | TEXT | `queued` \| `running` \| `completed` \| `failed` |
| pipeline_state | JSONB | per-stage progress for live UI |
| summary | JSONB | arch classification, issues (circular deps, coupling, global state) |
| created_at | TIMESTAMPTZ | |

### `chunks` + `embeddings` (pgvector)
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| repository_id | FK | |
| entity_id | FK NULL | nullable for module-level chunks |
| level | TEXT | `module` \| `class` \| `function` |
| content | TEXT | the chunk text |
| embedding | vector(1536) | configurable dims |

pgvector index: HNSW on `embedding`.

### `test_runs`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| repository_id | FK | |
| status | TEXT | `queued` \| `running` \| `passed` \| `failed` |
| tests_generated / tests_passed / tests_failed | INTEGER | |
| line_coverage / branch_coverage | NUMERIC(5,2) | percent |
| target_reached | BOOLEAN | line_coverage > 60 |
| log | TEXT | truncated sandbox output |
| created_at | TIMESTAMPTZ | |

### `test_cases`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| test_run_id | FK | |
| name | TEXT | |
| target_entity_id | FK NULL | function under test |
| status | TEXT | `passed` \| `failed` \| `skipped` |
| coverage_line_nums | INTEGER[] | lines this test covered |
| duration_ms | INTEGER | |

### `refactor_proposals`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| repository_id | FK | |
| entity_id | FK NULL | target |
| original_code / proposed_code | TEXT | |
| rationale | JSONB | why items |
| breaking_changes | JSONB | list: entity, impact (`high/med/low`), reason, affected callers (`file:line`) |
| safety_score | JSONB | total, api_compat, test_compat, dependency_impact, behavioral_risk |
| risk_level | TEXT | `low` \| `medium` \| `high` |

## API contract (v1) — routes

- `POST /api/v1/repositories/upload` — multipart ZIP → repository id, begins scan.
- `POST /api/v1/repositories/import` — body `{ "github_url": "..." }`.
- `GET /api/v1/repositories/{id}` — metadata + status.
- `GET /api/v1/repositories/{id}/graph` — nodes/edges for React Flow (`{ nodes: [{id, label, type, complexity, file}], edges: [{source, target}] }`).
- `GET /api/v1/repositories/{id}/entities/{entityId}` — entity metadata + AST facts.
- `GET /api/v1/repositories/{id}/entities/{entityId}/explanation` — structured LLM explanation with `evidence[]` (`{ claim, file, line_start, line_end, code }`).
- `GET /api/v1/repositories/{id}/entities/{entityId}/impact` — callers + impact level.
- `POST /api/v1/repositories/{id}/tests/generate` — starts test generation job.
- `GET /api/v1/repositories/{id}/tests/latest` — coverage summary + uncovered lines.
- `POST /api/v1/repositories/{id}/tests/generate-uncovered` — targeted iteration.
- `POST /api/v1/repositories/{id}/refactors/{entityId}/propose` — LLM + static diff → proposal.
- `GET /api/v1/repositories/{id}/refactors` — list proposals + safety scores.
- `GET /api/v1/repositories/{id}/search?q=...` — semantic search (pgvector).

Shared envelope: `{ "data": ..., "error": null }`; errors: `{ "data": null, "error": { "code": "...", "message": "..." } }`.

## Evidence-citing contract

Every AI explanation returns `evidence` entries, which the frontend renders as clickable `file:line` links into the Monaco viewer. This is a hard requirement, not optional.
