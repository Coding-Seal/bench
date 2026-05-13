# Thesis — Typst Reference

## Build

```bash
just thesis          # compile → thesis/thesis.pdf
just thesis-watch    # recompile on save (uses typst watch)

# or directly (typst binary is at ~/.cargo/bin/typst)
~/.cargo/bin/typst compile main.typ thesis.pdf
~/.cargo/bin/typst watch main.typ thesis.pdf
```

Requires Typst ≥ 0.14.0. Binary installed via `cargo install typst-cli`.

## Thesis metadata

- **Topic:** Байесовская оптимизация конфигурационных параметров PostgreSQL
- **Type:** Выпускная квалификационная работа бакалавра
- **University:** СПбПУ Петра Великого, direction 09.03.04
- **Language:** Russian
- **Standard:** ГОСТ 7.32-2017 (НИР report format, adapted for VKR)
- **Template:** `@preview/modern-g7-32:0.2.0`

Fill in before defence:
- `main.typ` → `manager: (name: "...", position: "...")`
- `main.typ` → `performers: ((name: "...", position: "Студент гр. ХХХХ"),)`

## File structure

```
thesis/
├── main.typ                   # entry point — all gost.with() params here
├── references.bib             # BibTeX bibliography (12 sources)
├── docs/                      # template docs (gitignored)
└── chapters/
    ├── abbreviations.typ      # body only — heading added in main.typ
    ├── intro.typ              # body only — = Введение in main.typ
    ├── ch1-analysis.typ       # == subsections; no top-level = heading
    ├── ch2-bayesian.typ
    ├── ch3-implementation.typ
    ├── ch4-experiments.typ
    └── conclusion.typ         # body only — = Заключение in main.typ
```

Chapter files contain `==` and `===` headings only — the `=` section heading
lives in `main.typ`. Exception: `intro.typ` and `conclusion.typ` have no
headings at all (Введение/Заключение are structural elements, not numbered
sections).

---

## Template: modern-g7-32

Docs are in `thesis/docs/gost/`. Key reference files:
- `quick-start.mdx` — overview
- `reference/title.mdx` — gost.with() params
- `reference/abstract.mdx`, `performers.mdx`, `outline.mdx`, `body.mdx`
- `reference/elements/` — table, equation, image, code, enum

### Import

```typst
#import "@preview/modern-g7-32:0.2.0": gost, abstract, appendixes
```

### gost.with() — all parameters used

```typst
#show: gost.with(
  ministry: "Министерство науки и высшего образования Российской Федерации",
  organization: (
    full: "Санкт-Петербургский политехнический университет Петра Великого",
    short: "СПбПУ",
  ),
  report-type: "ВЫПУСКНАЯ КВАЛИФИКАЦИОННАЯ РАБОТА",  // default is "ОТЧЕТ"
  about: "бакалавра",          // line under report-type on title page
  subject: "Тема работы",      // topic — shown on title page
  bare-subject: true,          // suppresses "по теме:" prefix before subject
  // research: "..."           // НИР name — omit for VKR (bare-subject: true)
  manager: (
    name: "Фамилия И.О.",
    position: "д-р техн. наук, доцент",
    title: "Научный руководитель,",  // prefix line above name
  ),
  performers: (
    (name: "Фамилия И.О.", position: "Студент гр. ХХХХ"),
    // single performer → appears on title page, no separate page
    // multiple performers → separate "СПИСОК ИСПОЛНИТЕЛЕЙ" page
  ),
  city: "Санкт-Петербург",
  year: 2026,                  // auto uses current year
  // add-pagebreaks: true      // default: = headings start on new page
  // text-size: (default: 14pt, small: 10pt)  // ГОСТ default
  // indent: 1.25cm            // ГОСТ default
)
```

### Structural headings

The template recognises these `=` heading texts as ГОСТ structural elements
(no number, centred, uppercase, new page before each):

```
Перечень сокращений и обозначений
Термины и определения
Введение
Заключение
Список использованных источников
Приложение
```

**Never** put `==` subsections inside Введение or Заключение — since those
headings are unnumbered, child headings get numbered "0.1", "0.2" etc. Use
bold inline labels instead: `*Актуальность темы.*`

### Abstract

```typst
#abstract(
  "ключевое слово",   // 5–15 keywords, positional args
  "второе слово",
)[
  Текст реферата до 850 знаков...
]
```

Auto-counts pages, figures, tables, sources. Pass `count: false` to disable.

### Outline (table of contents)

```typst
#outline()           // depth: 3 by default
#outline(depth: 2)   // show only = and == headings
```

### Bibliography

```typst
#bibliography("references.bib")
// template auto-applies gost-r-705-2008-numeric style
// DO NOT pass style: explicitly — template sets it
```

Cite with `@key`. Multiple: `@key1 @key2`. In text renders as `[1]`, `[1, 2]`.

---

## Typst syntax reference

### Math — differences from LaTeX

| LaTeX       | Typst      |
|-------------|------------|
| `\leq`      | `lt.eq`    |
| `\geq`      | `gt.eq`    |
| `\sim`      | `tilde`    |
| `\cdot`     | `dot`      |
| `\frac{a}{b}` | `a / b`  |
| `\overline{x}` | `overline(x)` |
| `\bar{x}`   | `overline(x)` |
| `x_{\text{sub}}` | `x_"sub"` |
| `\text{word}` | `"word"` |
| `a \leq b`  | `a lt.eq b` |

**Strings in math:** use `"text"` — NO backslash escaping inside. Write
`"max_parallel_workers"` not `"max\_parallel\_workers"`.

**Display equation** (numbered, on its own line): surround with spaces:
```typst
$ formula $
```

**Inline equation:** `$formula$` (no surrounding spaces)

**"Где" clause** (ГОСТ 6.8.2 — define symbols after formula):
```typst
$ E = m c^2 $ <eq-label>

где $E$ --- энергия объекта; \
$m$ --- его масса; \
$c$ --- скорость света в вакууме.
```

Use `\` for line breaks within the где block. First line starts with `где`
(no colon, no uppercase).

**Suppress equation number** for a single equation (use sparingly — ГОСТ
requires all equations to be numbered):
```typst
#[
  #set math.equation(numbering: none)
  $ long formula $
]
```

**Reference a formula in text:**
```typst
как показано в формуле @eq-label  // renders as "в формуле (1)"
```

### Tables

```typst
#figure(
  table(
    columns: (2fr, 1fr, 2fr),    // prefer fr over auto for body columns
    align: (left, center, left),
    table.header[*Параметр*][*Диапазон*][*Описание*],
    [строка], [значение], [описание],
  ),
  caption: [Название таблицы],
) <table-label>
```

**Column sizing rules:**
- `auto` in first column + long monospace names → overflow. Use `fr` instead.
- `max_parallel_workers_per_gather` (32 chars) needs ~70 mm at 10pt mono.
  With A4 text width ~165 mm, use `columns: (3fr, 0.8fr, 3fr)` to fit it.
- For header text overflow with 5 columns, use all-`fr`:
  `columns: (2fr, 1fr, 1.5fr, 1.5fr, 1.5fr)`.
- Force header line breaks with `\ `: `[*Учёт \ нагрузки*]`.

Table caption is placed **above** the table automatically by the template
(ГОСТ 6.6.3). Do not use `#figure(placement: top)`.

Inside very wide tables, use `#set text(size: 10pt)` to allow smaller font
(ГОСТ 6.6.7 permits it).

### Figures / images

```typst
#figure(
  image("sources/architecture.svg", width: 80%),
  caption: [Архитектура системы],
) <fig-label>

// Reference in text:
как показано на рисунке @fig-label   // renders as "на рисунке 1"
```

Supported formats: PNG, JPEG, SVG, PDF.

### Code blocks (listings)

```typst
#figure(
  ```python
  def hello():
      pass
  ```,
  caption: [Листинг функции],
) <lst-label>
```

### Enumerated lists (ГОСТ-compliant)

```typst
+ первый пункт;        // ordered list with semicolons
+ второй пункт;
+ третий пункт.

- маркированный;       // unordered list
- второй элемент.
```

### Cross-references

```typst
@label          // figure/table/equation → "рисунок 1" / "таблица 1" / "(1)"
@source-key     // bibliography → "[1]"
```

### Structure heading (custom)

For non-standard structural titles (e.g. university-specific):
```typst
#import "@preview/modern-g7-32:0.2.0": structure-heading
#structure-heading[Заголовок без номера]
```

---

## Thesis content summary

**Chapter 1 — Анализ предметной области**
Literature review: manual tuning, pgTune (heuristic), OtterTune (ML, unmaintained),
Azure Auto Tuning (proprietary). Comparison table. Gap: no open, maintained,
workload-aware tool.

**Chapter 2 — Байесовская оптимизация как метод настройки СУБД**
Black-box optimisation formulation. BO loop (surrogate + acquisition). TPE
algorithm (Optuna). SMAC algorithm (random forest surrogate, intensification).
Search space: 25 params across 5 categories (memory, WAL, planner/IO, bgwriter,
connections/parallelism). Parallel-worker hierarchy enforced by clipping.
Metrics: TPS via `pg_stat_database_xact_commit` rate; latency via active_time/xact_commit.
Prometheus window trimmed ±2.5% to avoid `rate()[1m]` bleed.

**Chapter 3 — Архитектура и реализация системы**
5 components: Optimizer (Optuna+SMAC), Agent (pg_manager.py), Metrics Store
(Prometheus), Load Generator (pgbench), PostgreSQL. Docker isolation (CPU cores
2-5, 4 GB RAM). Two-level config: `postgresql.conf` includes `performance.conf`.
Trial flow: backup → apply → restart/reload → sleep 5s → pgbench → sleep 15s →
query Prometheus → tell. pgTune baseline injected via `study.add_trial()`
(not `enqueue_trial()` — avoids SMAC intensifier assertion). Warmup run before
trial 0. 44 unit tests.

**Chapter 4 — Апробация и анализ результатов**
60 SMAC iterations, OLTP TPC-B, 120s runs, 20 clients/threads. Hardware: 6-core
Linux workstation, SSD NVMe, 16 GB RAM (container limited to 4 GB).
Result: **+10% TPS vs pgTune baseline**. 70% of gain in first 20 iterations.
Key params: `shared_buffers` → upper range (1536–2048 MB); `checkpoint_completion_target`
≥ 0.9; `jit = off` for OLTP; `wal_compression = lz4/zstd`.

---

## Common pitfalls

- `typst` not on PATH after fresh shell — binary is at `~/.cargo/bin/typst`.
  Run `source ~/.zshrc` or use `just thesis`.
- Typst math strings need NO backslash escaping: `"active_time_seconds_total"` ✓
- `==` under `= Введение` generates "0.1" numbering — use bold text instead.
- SMAC needs `optunahub` installed (`uv sync` handles this).
- pgTune baseline must use `study.add_trial()`, not `enqueue_trial()`.
- `#bibliography("references.bib")` — no `style:` argument; template sets ГОСТ.
