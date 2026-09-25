# User documentation information architecture

Status: **design contract for issues #165–#173**, based on the repository at `626dd3b` (2026-09-16). This document governs future documentation changes; it is not itself the user guide. Agora 1.0's frozen release/publication scope remains controlled by [#148](https://github.com/alexsosn/Agora/issues/148). Do not treat proposed pages below as already shipped.

## Evidence and design decision

The current [README](../../README.md) gives a workable first install, plugin chooser and seed prompts, but its documentation list places researcher tasks beside release plans, architecture and contributor material. The [wiki index](../README.md) is a project knowledge-base map, not a researcher entry point. [Installation](../guides/installation.md) mixes normal use with local development, cache reference and troubleshooting; [compatibility](../guides/compatibility.md) leads with verification taxonomy; the [cache guide](../guides/context-fabric-cache.md) combines a safe first-load workflow with detailed operational reference. There is no dedicated researcher landing page, per-plugin user page, tutorial set, or human-readable projection of all registered resources. The README's prompts are examples, not demonstrated start-to-success tutorials.

External patterns consulted:

- [Diátaxis: four kinds of documentation](https://diataxis.fr/start-here/) separates learning-oriented tutorials, task-oriented how-to, factual reference and explanatory material. Use the roles as a writing test, not as mandatory directory names or a website framework.
- [Python Packaging User Guide](https://packaging.python.org/en/latest/index.html) exposes tutorials, guides, explanations and reference as distinct destinations. Its user/builder distinction also argues against mixing installation with contribution instructions.
- [Claude Code: discover/install plugins](https://code.claude.com/docs/en/discover-plugins) separates adding a marketplace from choosing and installing a plugin, and places installed-plugin lifecycle in the host. Agora documents only its specific repository/plugin IDs and constraints; the host remains authoritative for changing UI and generic lifecycle semantics.

**Decision:** Keep GitHub Markdown and existing `wiki/` conventions. Make one goal-oriented researcher landing page (#165) the primary destination from README; reserve the existing wiki index for repository navigation. Add static user-facing pages/projections only where a documented user journey needs them. Do not create a docs database, navigation runtime, site generator or speculative search UI in #164.

## Audiences and journeys

The primary reader is a **researcher** choosing and using a scholarly capability. A **returning researcher** needs status, provenance/reproducibility, updates and recovery. Contributors/maintainers use a separate secondary path; personas need no further split by host or discipline at the top level because plugin and resource detail pages can carry those differences.

Paths below start at the repository README. `Current` describes links actually available now, or identifies where a link is **missing**; `Target` names *future roles* with implementing tickets, not extant hyperlinks. A repository file-browser search or an installed plugin's resource discovery is a workaround, not a working documentation navigation path.

| User question / journey | Current shortest available path and gap | Target shortest path and success test |
|---|---|---|
| Does Agora have a resource for my research question? | README → “Choosing a plugin” identifies Context-Fabric, but there is **no linked path from README to a complete resource catalog or a Targum entry**. A user must inspect `registry/resources.yaml` manually through the repository tree or install the plugin and discover its resources. Neither is an adequate documentation path. | README → user guide (#165) → generated resource catalog (#167) → resource entry with provider/plugin and scope. Answer presence and what to install without YAML. |
| Which plugin/resource do I choose? | README → “Choosing a plugin” → installation section/guide; four families are distinguishable, but corpus members and per-plugin constraints require other files. | README → user guide → plugin chooser (#165/#166) or catalog (#167) → plugin detail (#168) → install. Show local/remote, resource, license/provenance and caveats *before* installation. |
| Can I install and reach one successful operation? | README installation section → **README's own example prompts** is the shortest current path. The linked installation guide gives details but does **not** link back to those prompts or provide a bounded first-success tutorial for each family. | README → user guide → installation how-to (#172, retaining #150 facts) → family tutorial (#170). The tutorial includes prerequisites, exact bounded task, expected result and next step. |
| What can it do, what will it cost, and can I trust this result? | README → compatibility; Context-Fabric cost requires installation/cache guide or registry; scholarly skill text is within plugin packages. “Verified” is integration evidence, not data certification. | README → user guide → catalog/resource or plugin page (#167/#168) → decision-first compatibility (#171), source-backed guidance (#169) and cost/cache reference. State observation context and licensing uncertainty rather than guaranteed cost/quality. |
| How do I recover from failure or excessive resource cost? | README → installation → bottom troubleshooting or cache guide; users must guess the right subsystem/section. | README → user guide → symptom-based troubleshooting (#172) → safe next action → relevant host/upstream/cache reference. Distinguish upstream outages from Agora integration faults. |
| How do I update/remove, resume work, or reproduce results? | README → installation guide → Updating/Removing; Context-Fabric cache and resource provenance are separate. | User guide → task how-to (#172) for host-owned lifecycle or reproducibility recipe (#169/#170) → linked reference for source revision, settings, costs and cache. Never imply uninstall removes corpus data. |

The landing page may offer *Browse plugins* and *Browse resources* as distinct entry points. The former answers which tool/service to install; the latter answers whether a particular corpus or dataset exists. Do not force researchers to know internal registry IDs to find either.

## Existing surface ownership and migration classification

| Current surface | Audience / role | Treatment |
|---|---|---|
| Root `README.md` | Mixed project front door, short plugin chooser/install, seed prompts, secondary contributor exits | Preserve truthful first-use content until #165. Then link prominently to researcher landing and shorten competing release/architecture exits; do not copy generated catalog facts here. |
| `wiki/README.md` | Maintainer/contributor index and document-history navigation | Keep as *project* index; do not repurpose it as the main researcher landing. Link both indices visibly once the user index exists; update stale release/governance pointers separately if needed. |
| `wiki/guides/installation.md` | Researcher installation/how-to plus contributor local testing, reference and troubleshooting | #172 separates researcher instructions from developer workflow, keeping host-owned update/remove and safe first-load instructions. |
| `wiki/guides/compatibility.md` | Researcher decision/reference plus maintainer verification methodology | #171 puts factual plugin/client/platform decisions first, then evidence/check IDs; retains explicit source and scope boundaries. |
| `wiki/guides/context-fabric-cache.md` | Researcher cost/recovery how-to plus detailed operational reference | Keep one authoritative cost/cache destination; link concise extracts from relevant pages rather than copy changing limits and measurements. |
| `plugins/README.md`; plugin manifests/launch metadata | Contributor integration reference and generated host artifacts | Not plugin detail pages. #168 creates researcher-facing pages with canonical metadata links/projection. Never hand-edit generated manifests. |
| `plugins/*/skills/*/SKILL.md` and upstream plugin skills | Canonical agent-facing behavior; some reusable human scholarly guidance | #169 audits human-useful sections and renders/links/shared-sources them without independent prose copies. Keep agent-only directives out of user navigation. |
| `registry/README.md`, `registry/*.yaml`, `registry/collections/`, schemas | Canonical machine metadata and maintainer reference | Source for #167 resource projection and structured #168 facts; don't make researchers inspect YAML. Collection members need clear resource identity and rights. |
| `wiki/architecture/*` (including this page) | Durable architecture, rationale and contributor design/reference | Secondary from README/wiki index; not first-use documentation. |
| `wiki/releases/*`, `wiki/backlog/*`, `wiki/reviews/*` | Release plans, planned/parked work, immutable historical audits | Historical/project tracking; never present as user how-to, evidence of *current* support or a user navigation prerequisite. |
| `CONTRIBUTING.md`, `AGENTS.md`, `.agents/skills/*`, `.github/*`, `scripts/`, `tests/`, `verification/` | Contributor/agent policy, implementation and test evidence | Remain reachable through contributing/project index; source of validation, not ordinary researcher navigation. |
| `profiles/`, `generated/`, `.claude-plugin/`, `.agents/plugins/` | Machine-selected bundles, generated/imported integration artifacts | Canonical/derived implementation assets, not hand-authored public docs. Describe resulting choices in plugin/resource pages only when relevant. |

## Page-role contract for subsequent tickets

| Role | Must answer / required content | Must not become |
|---|---|---|
| Researcher landing (#165) | Choose *get started, plugins, resources, tutorials, compatibility, troubleshooting* in one glance; secondary link to contributor/project index. | Long README, schema dump, release dashboard or duplicate registry catalog. |
| Plugin chooser and mental model (#165/#166) | Agora marketplace → installable plugin → scholarly resource when a plugin provides multiple corpora; skills guide agents. Answer “What installs for BHSA?” without internal vocabulary. | Universal claim that all plugins are Text-Fabric or that every resource is independently installable. |
| Resource catalog/entry (#167) | Generated from canonical registry: recognizable name, language/field, scope, plugin, acquisition, rights, integration caveats, measured cost *where available*. Explicitly handle collection/member, unknowns and component-specific rights. | Manually maintained duplicate YAML, data-quality ranking, promise that all 37 resources have identical status or costs. |
| Plugin detail (#168) | One consistent pre-install decision surface: use cases, service/resources, local/remote behavior, prerequisites, install, first success link, limitations, cost, license/provenance, authoritative upstream links, symptom links. | Upstream manual or mutable host UI copy; new capability promises. |
| Tutorial (#170) | After-install, one bounded task with exact starting state, steps, recognizable success signal, relevant interpretation caveat and next step. One per plugin family initially. | Exhaustive command catalog, unbounded expensive load, speculative unsupported operation. |
| How-to (#172) | A specific reader goal, prerequisites, safe steps and what to do on failure; include update/remove and caching workflows where needed. | Platform internals or broad conceptual discussion before the action. |
| Troubleshooting (#172) | Observable symptom → likely *class* of cause → safe next action → linked authoritative detail; provider failure vs Agora failure explicit. | Third-party semantic patch, guessed universal workaround or an error-code directory requiring internal knowledge. |
| Compatibility / factual reference (#171) | Client/transport/platform decision at top with bounded evidence, known user impact and provenance; technical check IDs below. | Permanent uptime guarantee, quality certification or extension to untested platform. |
| Explanation / scholarly guidance (#166/#169) | Small mental model or reusable documented interpretation guidance; authoritative skill/upstream source linked. | Agent-only instructions dumped verbatim or duplicated mutable upstream statements. |
| Contributor/architecture/reference (existing) | Normative boundaries, registry model, reproducible engineering evidence, designs and maintenance policy. | A compulsory detour in any first-time researcher journey. |

A document can contain a short contextual link to another role, but its *primary task* decides where it belongs. In particular, installation is a how-to, a first-result walkthrough is a tutorial, a resource list is generated reference, and a plugin overview is a pre-install decision page. Do not create four versions of the same mutable truth.

## Canonical facts, links and vocabulary

- **Registry owns:** plugin/provider/resource identity, versions and pins, resource/member relationships, supported client/transport metadata, controlled verification claims, known-issue references, data license/provenance evidence and historical load-cost records. Generate or refer to it; unknown means unknown. Where a status is derived from current CI observations, link the exact run/artifact and explain its date/revision; a YAML check definition is not a successful run.
- **Skill owns:** its agent behavioral instructions and source-specific research-method guidance. Reuse selected human-appropriate portions or a shared canonical fragment after #169's audit. No silent copy of complex morphology guidance.
- **Agora-owned guides own:** stable installation-specific examples, bounded first-success tasks, cost/cache workflows and symptom recovery; check claims against current runtime and registry. Documentation tests (#173) ensure links/projections don't drift.
- **External authorities own:** generic Claude/Codex marketplace UI/lifecycle, upstream plugin algorithms and scholarly interpretation, and external corpus documentation. Link to the authoritative current host/upstream page rather than reconstruct it in Agora.
- **Vocabulary on first contact:** *marketplace*, *plugin*, *resource/corpus*, *research guidance (skill)*. Say that Context-Fabric exposes selectable corpora; Perseus, Sefaria and SEDRA primarily expose services. Introduce *collection member* where it changes selection; *feature module* where it changes load/cost. Defer *provider*, *transport*, *materializer*, *snapshot*, *verification check ID*, registry fields and cache locks until the relevant decision/reference. Never hide a consequential cost, supported-client restriction or licensing limitation to avoid a technical term.

## Delivery and acceptance gates

1. #165 links the researcher landing from README without breaking #150's existing accurate first-success/install path; project index remains separate.
2. #166 sets the shared terminology and compact diagram before catalog/plugin pages lock their language.
3. #167 derives catalog entries from the canonical registry; #168 links to them rather than duplicating inventories; #169 reuses scholarly source text, and #170 builds tested bounded tutorials.
4. #171 makes support decisions visible before verification machinery; #172 puts observable recovery symptoms ahead of internal subsystem names.
5. #173 checks navigation/link integrity, generated freshness and five end-to-end *documentation* walkthroughs: Targum discovery, BHSA selection and first success, Perseus legacy CTS reliability, BHSA first-load cost, and Sefaria duplicate search interpretation. No walkthrough should require raw YAML, source code, backlog, release plans or architecture pages after delivery.

For each downstream PR, independently navigate from README as a newcomer: count clicks, unknown vocabulary and wrong turns; compare facts against current registry/skill/runtime evidence; confirm the target page's role is preserved. This design document alone cannot satisfy those future end-to-end criteria.
