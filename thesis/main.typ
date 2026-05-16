#import "@preview/modern-g7-32:0.2.0": gost, abstract, appendixes

#show: gost.with(
  ministry: [Министерство науки и высшего образования Российской Федерации \
Санкт-Петербургский политехнический университет Петра Великого \
Институт компьютерных наук и кибербезопасности \
Высшая школа программной инженерии],
  organization: (full: none, short: none),
  report-type: "ВЫПУСКНАЯ КВАЛИФИКАЦИОННАЯ РАБОТА",
  about: "бакалавра",
  research: "направление 09.03.04 «Программная инженерия»",
  subject: "Оптимизация конфигурации PostgreSQL на основе алгоритма SMAC",
  bare-subject: true,
  manager: (name: "Прокофьев О. В.", position: "старший преподаватель", title: "Научный руководитель,"),
  performers: ((name: "Ганиуллин Р. Р.", position: "Студент гр. 5130904/20104"),),
  city: "Санкт-Петербург",
  year: 2026,
)

// ── Реферат ───────────────────────────────────────────────────────────────────

#abstract(
  "PostgreSQL",
  "автоматическая настройка СУБД",
  "байесовская оптимизация",
  "SMAC",
  "TPE",
  "pgbench",
  "конфигурационные параметры",
)[
  Выпускная квалификационная работа посвящена разработке прототипа системы
  автоматической оптимизации конфигурационных параметров СУБД PostgreSQL.
  Предметом исследования являются методы автоматической настройки параметров
  СУБД с использованием байесовской оптимизации.

  В работе проведён анализ существующих подходов к настройке PostgreSQL,
  выявлены их ключевые недостатки. Разработана архитектура системы,
  включающая оптимизатор на основе фреймворка Optuna с сэмплерами SMAC и TPE,
  агент управления конфигурацией, генератор нагрузки pgbench и систему сбора
  метрик Prometheus. Сформировано пространство поиска из 25 конфигурационных
  параметров. Проведены эксперименты на трёх сценариях нагрузки: OLTP (TPS),
  OLTP (задержка) и OLAP (TPS), по три повторных запуска каждым сэмплером.
  SMAC достиг прироста +14,3\% TPS на OLTP-нагрузке и снижения задержки на
  31,2\% относительно конфигурации pgTune; TPE показал сопоставимые результаты.

  Результаты подтверждают применимость байесовской оптимизации для задач
  автоматической настройки СУБД и демонстрируют возможность создания
  открытого инструмента, превосходящего эвристические методы без участия эксперта.
]

// ── Abstract (English) ───────────────────────────────────────────────────────

#pagebreak()
#{
  show heading: it => align(center)[#upper(it.body)]
  heading(level: 1, numbering: none, outlined: false)[Abstract]
}

#v(0.5em)
#context {
  let pages = counter(page).final().first()
  let figs  = counter("image").final().first()
  let tabs  = counter("table").final().first()
  let refs  = query(selector(ref))
    .filter(it => it.element == none)
    .map(it => it.target)
    .dedup()
    .len()
  [Work: #pages p., #figs fig., #tabs tab., #refs ref.]
}

#set par(first-line-indent: 0pt)
#upper[PostgreSQL, automated DBMS configuration tuning, Bayesian optimization, SMAC, TPE, pgbench, configuration parameters]

This thesis presents a prototype system for automated optimization of PostgreSQL
DBMS configuration parameters using Bayesian optimization. The subject of study
is automated database tuning methods based on black-box optimization.

Existing approaches to PostgreSQL tuning are analyzed, and their key shortcomings
are identified. The proposed system architecture comprises an Optuna-based optimizer
with SMAC and TPE samplers, a configuration management agent, a pgbench load
generator, and a Prometheus metrics collection system. A search space of 25
configuration parameters was defined. Experiments were conducted on three workload
scenarios --- OLTP (TPS), OLTP (latency), and OLAP (TPS) --- with three independent
runs per sampler. SMAC achieved a +14.3% TPS improvement on OLTP workloads and a
31.2% latency reduction relative to the pgTune baseline; TPE showed comparable results.

The results confirm the applicability of Bayesian optimization for automated
DBMS tuning and demonstrate the feasibility of building an open-source tool that
outperforms heuristic methods without expert involvement.

// ── Оглавление ────────────────────────────────────────────────────────────────

#outline()

// ── Определения, обозначения и сокращения ────────────────────────────────────

= Перечень сокращений и обозначений

#include "chapters/abbreviations.typ"

// ── Введение ──────────────────────────────────────────────────────────────────

= Введение

#include "chapters/intro.typ"

// ── Глава 1 ───────────────────────────────────────────────────────────────────

= Анализ предметной области

#include "chapters/ch1-analysis.typ"

// ── Глава 2 ───────────────────────────────────────────────────────────────────

= Байесовская оптимизация как метод настройки СУБД

#include "chapters/ch2-bayesian.typ"

// ── Глава 3 ───────────────────────────────────────────────────────────────────

= Архитектура и реализация системы

#include "chapters/ch3-implementation.typ"

// ── Глава 4 ───────────────────────────────────────────────────────────────────

= Апробация и анализ результатов

#include "chapters/ch4-experiments.typ"

// ── Заключение ────────────────────────────────────────────────────────────────

= Заключение

#include "chapters/conclusion.typ"

// ── Список использованных источников ─────────────────────────────────────────

#bibliography("references.bib")
