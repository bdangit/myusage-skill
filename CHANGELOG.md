# Changelog

## [1.3.1](https://github.com/bdangit/myusage-skill/compare/v1.3.0...v1.3.1) (2026-04-14)


### Bug Fixes

* correct Codex label in CHANGELOG - Codex is OpenAI CLI, not Claude CLI ([515fe71](https://github.com/bdangit/myusage-skill/commit/515fe71fbb2909d17d9ea3f18351b990602ecbbf))

## [1.3.0](https://github.com/bdangit/myusage-skill/compare/v1.2.0...v1.3.0) (2026-04-14)


### Features

* add Codex (OpenAI CLI) platform support with message counts, token tracking, and rollout-based model resolution ([61faa1f](https://github.com/bdangit/myusage-skill/commit/61faa1f38a979175b6cba259d63843c13308247c))


### Bug Fixes

* correct Codex token column display and add Copilot CLI PRU extraction ([8d5cd68](https://github.com/bdangit/myusage-skill/commit/8d5cd68))
* count Codex messages from event_msg user_message events ([e8a122d](https://github.com/bdangit/myusage-skill/commit/e8a122d))
* preserve parsed PRU data in compute_session_costs for copilot_cli ([c0920da](https://github.com/bdangit/myusage-skill/commit/c0920da))
* skip tool_result entries in Claude Code message count ([cb7cb41](https://github.com/bdangit/myusage-skill/commit/cb7cb41))

## [1.2.0](https://github.com/bdangit/myusage-skill/compare/v1.1.3...v1.2.0) (2026-04-14)


### Features

* add squad infrastructure and team configuration ([2a25eef](https://github.com/bdangit/myusage-skill/commit/2a25eef4808685938302705f0d6c3d74439415b1))

## [1.1.3](https://github.com/bdangit/myusage-skill/compare/v1.1.2...v1.1.3) (2026-03-25)


### Bug Fixes

* enable /myusage slash command in Copilot CLI ([#20](https://github.com/bdangit/myusage-skill/issues/20)) ([2814bfe](https://github.com/bdangit/myusage-skill/commit/2814bfef44b061466049125ce1fff595815fba89))

## [1.1.2](https://github.com/bdangit/myusage-skill/compare/v1.1.1...v1.1.2) (2026-03-25)


### Bug Fixes

* add plugin manifest validation and fix marketplace.json schema error ([13d8e14](https://github.com/bdangit/myusage-skill/commit/13d8e14b921086eed95eb6b3ed775f6fdad84ab7))
* plugin manifest validation and dual-CLI install docs ([d15153d](https://github.com/bdangit/myusage-skill/commit/d15153d46e3a0e80a255cfa1606663587797cc65))

## [1.1.1](https://github.com/bdangit/myusage-skill/compare/v1.1.0...v1.1.1) (2026-03-24)


### Bug Fixes

* remove invalid platforms and requirements fields from plugin.json ([763742a](https://github.com/bdangit/myusage-skill/commit/763742ad3d8937ceea6eb3dac35f35f9417f6074))
* remove invalid platforms and requirements fields from plugin.json ([0b94781](https://github.com/bdangit/myusage-skill/commit/0b94781669d0f342bfcfa23ea79f1bbaec408666))

## [1.1.0](https://github.com/bdangit/myusage-skill/compare/v1.0.1...v1.1.0) (2026-03-24)


### Features

* **001:** implement AI usage insights report generator ([#2](https://github.com/bdangit/myusage-skill/issues/2)) ([bb138c5](https://github.com/bdangit/myusage-skill/commit/bb138c55ab8bf25a09c60cf26645c51b73c09883))
* **002:** add Copilot PRU and Claude token cost estimation to report ([0b773a0](https://github.com/bdangit/myusage-skill/commit/0b773a040b6149f085c06e161aa10b2bf26c5586))
* **002:** add PRU/token cost spec and LLM-agnostic constitution update ([72898a6](https://github.com/bdangit/myusage-skill/commit/72898a64af5fa7057192ec206c9b3b0162957ec1))
* **002:** PRU and token cost extraction with report display ([#4](https://github.com/bdangit/myusage-skill/issues/4)) ([0b773a0](https://github.com/bdangit/myusage-skill/commit/0b773a040b6149f085c06e161aa10b2bf26c5586))
* **003:** add marketplace install support + README preview assets ([#5](https://github.com/bdangit/myusage-skill/issues/5)) ([89faf1d](https://github.com/bdangit/myusage-skill/commit/89faf1d01e433635d5f513730857ef8726bf1214))
* **003:** GHA CI/CD pipeline spec ([#11](https://github.com/bdangit/myusage-skill/issues/11)) ([000d0e3](https://github.com/bdangit/myusage-skill/commit/000d0e3d4220fa908b8251c1ae08c263c8827dee))
* **003:** implement GHA CI/CD pipeline ([#13](https://github.com/bdangit/myusage-skill/issues/13)) ([73f4cb8](https://github.com/bdangit/myusage-skill/commit/73f4cb8e711be23f67138b665a23fb9ce5d82190))
* 5 enhancements — LLM-agnostic labels, 6-month default, AI themes, Claude modes, model normalization ([4755b5c](https://github.com/bdangit/myusage-skill/commit/4755b5c4d549d009c558941e9a54a02b04fed00a))
* **spec:** 002 — Copilot PRU and Claude token cost comparison ([#3](https://github.com/bdangit/myusage-skill/issues/3)) ([72898a6](https://github.com/bdangit/myusage-skill/commit/72898a64af5fa7057192ec206c9b3b0162957ec1))


### Bug Fixes

* **marketplace:** use github source object instead of invalid '.' string ([#6](https://github.com/bdangit/myusage-skill/issues/6)) ([3c4dbab](https://github.com/bdangit/myusage-skill/commit/3c4dbabfcb045aa32bd90dd1b42f6ed1bc10cd15))
* **marketplace:** use relative path string for source field ([#7](https://github.com/bdangit/myusage-skill/issues/7)) ([11b4e42](https://github.com/bdangit/myusage-skill/commit/11b4e429394c7318f9a3f0122d8a090f2dc67895))
