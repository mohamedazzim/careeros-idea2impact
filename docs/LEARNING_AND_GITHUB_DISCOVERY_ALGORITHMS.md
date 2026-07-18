# CareerOS Learning and GitHub Discovery Algorithms

Last verified from source code: 2026-06-19

## Source anchors

| Area | Primary files |
|---|---|
| GitHub repo / issue discovery | `backend/src/integrations/github/repo_discovery.py`, `backend/src/services/learning/github_project_service.py`, `backend/src/api/v1/endpoints/learning.py`, `frontend/src/components/learning/GitHubProjectsPanel.tsx` |
| Web / Coursera / Udemy discovery | `backend/src/integrations/learning/discovery.py`, `backend/src/services/learning/learning_resource_service.py`, `backend/src/services/learning/learning_path_service.py`, `frontend/src/components/learning/LearningPathsPanel.tsx`, `frontend/src/components/learning/GapActionsPanel.tsx` |
| YouTube discovery | `backend/src/integrations/youtube/client.py`, `backend/src/integrations/learning/discovery.py`, `backend/src/services/learning/learning_resource_service.py` |
| Shared learning ranking | `backend/src/services/learning/learning_resource_service.py`, `backend/src/services/learning/learning_path_service.py`, `backend/src/services/learning/gap_action_service.py` |
| Shared skill normalization | `backend/src/services/learning/skill_normalizer.py` |

## 1. Overview

CareerOS uses two different discovery systems for learning content:

1. **Learning resource discovery** for curated and live education sources such as seed data, YouTube, web search, Coursera, and Udemy.
2. **GitHub project discovery** for public repositories and beginner-friendly issues that match a user's missing skills.

Both systems are driven by skill gaps. The backend extracts missing skills from job matches, normalizes those skills, then asks one or more providers to discover candidates. Results are filtered, ranked, persisted or cached, and then surfaced to the frontend.

Important implementation note:

- The current code does **not** use a private GitHub repo index.
- The current code does **not** rank learning results by Google reviews.
- GitHub repository ranking uses GitHub repository metadata such as stars, template markers, and recency.
- Web learning discovery uses trusted domains, free-signal checks, and URL verification.

## 2. Skill normalization

Shared skill normalization lives in `backend/src/services/learning/skill_normalizer.py` and is used before discovery starts.

### What it does

- Normalizes aliases such as AWS, C++, JavaScript, Java, CI/CD, and similar variants into canonical slugs.
- Preserves distinct skills when the code intentionally treats them separately.
- Produces a display name and a slug that downstream services reuse for queries, cache keys, and UI labels.

### Why it matters

Skill normalization keeps the discovery queries stable. For example:

- `c++` maps to the GitHub search variant `cpp OR "c++"`.
- `ci/cd` maps to `ci/cd`, `ci-cd`, and `ci cd` variants.
- Java and JavaScript are kept separate so the search does not merge unrelated results.

## 3. Learning resource discovery flow

File anchors:

- `backend/src/services/learning/learning_resource_service.py`
- `backend/src/integrations/learning/discovery.py`
- `backend/src/integrations/youtube/client.py`

### End-to-end flow

1. The backend loads seed resources from `backend/seeds/learning_resources.json`.
2. If discovery is enabled, it asks the configured providers to search for live resources.
3. Each provider returns candidates with trust, relevance, freshness, and verification metadata.
4. The service deduplicates by URL, filters to valid HTTP(S) sources, and stores the results.
5. `get_resources_for_skill()` returns only free resources ordered by trust, relevance, freshness, verification time, and creation time.

### Ordering used for stored learning resources

`get_resources_for_skill()` sorts by:

1. `trust_score DESC`
2. `relevance_score DESC`
3. `freshness_score DESC`
4. `last_verified_at DESC NULLS LAST`
5. `created_at DESC`

That means the display order is not random and is not based on Google reviews. It is an internal CareerOS ranking.

## 4. YouTube discovery

File anchors:

- `backend/src/integrations/youtube/client.py`
- `backend/src/integrations/learning/discovery.py`

### Algorithm summary

- Uses the official **YouTube Data API v3**.
- Reads the API key from `YOUTUBE_API_KEY`.
- Searches with the query pattern:
  - `"{skill_name} free tutorial"`
- Searches **videos only**.
- Fetches video details after search so it can read duration and channel metadata.
- Keeps only videos from trusted channel matches when the skill-specific channel hints match.

### What metadata is used

- `video_id`
- `published_at`
- `channel_title`
- `duration_minutes`
- `last_verified_at`
- `search_query`

### Ranking behavior

YouTube itself returns results ordered by YouTube relevance. CareerOS then:

- filters to trusted channels,
- keeps verified results only,
- assigns internal trust/relevance/freshness scores,
- and later orders stored resources using the shared learning-resource ranking.

### Error handling

- If the API key is missing, the provider returns no results.
- If YouTube returns a quota error, the provider marks the status as quota-exceeded and returns no results.
- Other failures are logged and treated as soft failures.

## 5. Web search discovery

File anchors:

- `backend/src/integrations/learning/discovery.py`
- `backend/src/services/learning/learning_resource_service.py`

### Which provider is used

The selected backend comes from `LEARNING_WEB_SEARCH_PROVIDER`.

Supported values in code:

- `bing`
- `tavily`
- `serpapi`

Special case:

- `brave` is normalized to `bing`.

### What happens if multiple keys exist

The code does **not** auto-pick the best available provider from all configured keys. It uses the provider chosen by `LEARNING_WEB_SEARCH_PROVIDER`, then that provider checks whether its required key is configured.

### Search query generation

Web providers use skill-aware query templates. Examples from code:

- `"{skill_name} tutorial"`
- `"{skill_name} guide"`
- Coursera queries like `site:coursera.org "{skill_name}" free course`
- Udemy queries like `site:udemy.com "{skill_name}" free course`

### Trusted domains

The code only accepts URLs from trusted domains such as:

- `aws.amazon.com`
- `docs.aws.amazon.com`
- `dev.java`
- `docs.oracle.com`
- `openjdk.org`
- `spring.io`
- `jetbrains.com`
- `freecodecamp.org`
- `learn.microsoft.com`
- `codecademy.com`
- `edx.org`
- `developer.mozilla.org`
- `docs.docker.com`
- `fastapi.tiangolo.com`
- `git-scm.com`
- `kubernetes.io`
- `www.postgresql.org`
- `python.langchain.com`
- `docs.langchain.com`
- `react.dev`
- `www.tensorflow.org`
- `docs.pytorch.org`
- `www.youtube.com`
- `coursera.org`
- `www.coursera.org`
- `udemy.com`
- `www.udemy.com`

### URL verification and rejection rules

Before a result is accepted, the provider:

1. Resolves Bing redirect URLs.
2. Confirms the URL host is in the allowed domain set.
3. Optionally checks that the text looks free when the provider requires a free signal.
4. Verifies the URL with an HTTP GET.
5. Rejects items that fail verification or do not match the skill text.

### Ranking behavior

The web provider itself returns candidates in the order it discovers them, but each candidate is assigned:

- `trust_score`
- `relevance_score`
- `freshness_score`
- `last_verified_at`
- metadata such as `verification_status`, `price_status`, and `search_query`

After persistence, `get_resources_for_skill()` re-sorts by the shared learning-resource ranking.

### Is result order based on Google reviews?

No. The current code does not use Google reviews for learning-resource ranking.

### Is result order based on star count?

Not for normal web resources. Star count is not part of web-resource ranking unless the resource happens to be a GitHub repository and is handled by the GitHub discovery path.

### Is result order based on provider ranking?

Partly. Provider-specific trust/relevance/freshness scores influence final ordering after the backend persists or returns resources.

### Is result order based on custom CareerOS scoring?

Yes. The final display order is a CareerOS scoring and sorting decision, not the source provider's raw ranking alone.

## 6. Udemy/Coursera handling

File anchors:

- `backend/src/integrations/learning/discovery.py`
- `backend/src/services/learning/learning_resource_service.py`

### Current implementation

Coursera and Udemy are handled through web search discovery, not through dedicated official partner APIs in the current code.

- Coursera uses Bing/Tavily/SerpAPI web search with `site:coursera.org` filters.
- Udemy uses Bing/Tavily/SerpAPI web search with `site:udemy.com` filters.

### Price and free handling

- The code looks for free-signal markers such as `free`, `audit`, `open source`, and similar text.
- `price_status` is stored in metadata.
- If the price is unknown, the record is kept with a best-effort status such as `paid_or_unknown`, `verified_paid_or_unknown`, or `unverified`, depending on provider and verification state.

### What is not implemented yet

- No official Udemy API integration.
- No official Coursera partner API integration.
- No premium purchase flow.
- No affiliate monetization logic.

## 7. GitHub repo discovery

File anchors:

- `backend/src/integrations/github/repo_discovery.py`
- `backend/src/services/learning/github_project_service.py`
- `backend/src/api/v1/endpoints/learning.py`
- `frontend/src/components/learning/GitHubProjectsPanel.tsx`

### Frontend to backend flow

The frontend panel calls:

- `GET /api/v1/learning/github-projects`
- `POST /api/v1/learning/github-projects/refresh`

The backend service turns the user's missing skills into GitHub search queries and returns per-skill repository, template, and issue cards.

### GitHub API endpoints used

The implementation uses the public GitHub Search API:

- `GET /search/repositories`
- `GET /search/issues`

### Authentication behavior

- If `GITHUB_TOKEN` is configured, requests include a GitHub bearer token.
- If no token is configured, the code falls back to public anonymous GitHub search.
- If a token fails and the error looks like an auth/token problem, the provider can fall back to anonymous search once.

### Search queries generated per skill

Repo search queries follow this pattern:

- Template variant:
  - `({term}) template in:name,description,readme fork:false archived:false stars:>0`
- Normal project variant:
  - `({term}) in:name,description,readme fork:false archived:false stars:>0`

The skill term is normalized first. Important special cases:

- C++ becomes `cpp OR "c++"`
- CI/CD becomes `"ci/cd" OR "ci-cd" OR "ci cd"`
- JavaScript becomes `"javascript" OR js"`
- Java-family synonyms collapse to `java`

### How repositories are filtered

Repositories are filtered by the GitHub query itself and then by CareerOS normalization:

- forked repositories are excluded by query
- archived repositories are excluded by query
- empty results are discarded
- duplicate `full_name` values are deduplicated

### How repositories are ranked

The repository score uses:

- GitHub star count as the base score
- a bonus when the name or description suggests a template/starter/boilerplate/example/blueprint
- a larger bonus when `is_template` is true
- a large penalty for archived repositories
- `updated_at` is used as the final sort component

So for GitHub repo cards, **stars do matter**.

### How good-first-issues are searched

The issue query is:

- `({term}) is:issue state:open label:"good first issue","help wanted"`

Then the provider:

- discards pull requests,
- adds a score bonus for `good first issue`,
- adds a smaller bonus for `help wanted`,
- and sorts issues by the resulting score.

### Rate limit handling

- `403` or `429` with rate-limit headers/message is treated as a rate limit error.
- The provider reports `rate_limited` in its status.
- Non-rate auth failures are surfaced separately and may fall back to anonymous search.

### Provider health returned

The GitHub provider health object includes:

- `enabled`
- `provider`
- `provider_mode`
- `status`
- `cache_ttl_hours`
- `min_results_per_skill`
- `max_results_per_skill`
- `issue_discovery_enabled`
- `token_configured`
- `message`
- nested provider status details

### What is cached

`backend/src/services/learning/github_project_service.py` caches the final per-skill discovery payload in Redis with a key like:

- `learning_github_projects:{digest}`

The cache TTL is controlled by `GITHUB_REPO_CACHE_TTL_HOURS`.

## 8. GitHub issue discovery

File anchors:

- `backend/src/integrations/github/repo_discovery.py`
- `backend/src/services/learning/github_project_service.py`

### Algorithm summary

Issue discovery is tied to the same skill search term used for repositories. The provider searches open issues with the `good first issue` and `help wanted` labels. Pull requests are excluded. Results are ranked by GitHub search score plus label bonuses.

### What this means in practice

The system is not building a local issue graph. It is using the public GitHub Search API and then applying a CareerOS ranking layer.

## 9. Ranking and ordering logic

### Learning resources

Final ordering for stored learning resources comes from:

1. `trust_score`
2. `relevance_score`
3. `freshness_score`
4. `last_verified_at`
5. `created_at`

This ranking is used for the learning paths and gap-action views.

### GitHub repositories

Repository ranking is primarily:

1. GitHub stars
2. Template/starter-like signals
3. `is_template`
4. `updated_at`

### GitHub issues

Issue ranking is:

1. GitHub Search API score
2. `good first issue` bonus
3. `help wanted` bonus

### Provider ranking

Provider ranking is not a global opaque rank. CareerOS uses provider-specific trust and relevance scoring, plus internal sorting after persistence.

## 10. Provider health and failure handling

File anchors:

- `backend/src/services/learning/learning_resource_service.py`
- `backend/src/services/learning/learning_path_service.py`
- `backend/src/services/learning/gap_action_service.py`
- `backend/src/services/learning/github_project_service.py`

### Provider health behavior

The UI surfaces provider health so users can tell whether the backend:

- succeeded,
- skipped a provider,
- hit a missing API key,
- hit a quota error,
- or returned a partial result set.

### Failure handling

The services are designed to be soft-fail, not hard-fail:

- one provider can fail while others still return results,
- quota errors are reported,
- empty resources fall back to seed data or generated ideas,
- path and gap-action builders still return useful per-skill cards when possible.

### Frontend behavior

The frontend learning panels pass the user's selected missing skills to backend endpoints and render per-skill cards:

- `GitHubProjectsPanel.tsx` sends skills and optional `job_id` to the GitHub projects API.
- `LearningPathsPanel.tsx` sends skills and optional `job_id` to the learning paths API.
- `GapActionsPanel.tsx` sends skills and optional `job_id` to the gap-actions API.

UI behavior that follows from the backend responses:

- If a skill has no resources, the panel still shows the skill card and the backend message explains the lack of resources.
- If one skill fails but others succeed, the successful skills are still rendered.
- Provider health pills show status for each provider.
- The panels use wrapping and overflow-safe layouts so long titles and repo names stay inside cards.
- A global empty state should only appear when the backend truly returns no skill cards at all.

## 11. Caching behavior

### GitHub projects

Cached in Redis by digest key. This is the main explicit runtime cache in the code examined here.

### Learning resources and paths

The learning-resource and learning-path flows rely mostly on persisted database records and provider health state rather than a separate Redis result cache in the code inspected.

### YouTube and web providers

The provider objects keep last-run status in memory for health reporting, but they do not implement a broad persistent search-result cache in the provider layer.

## 12. Will my own GitHub repo appear?

### Short answer

**Maybe, but only if it is public and matches the search terms.**

### What the current implementation actually does

The GitHub finder uses generic public GitHub search for repositories and issues. It does **not** load the current user's repository list, and it does **not** have a connected GitHub account ingestion flow.

### Practical outcomes

- **Public repo:** can appear if it matches the skill query, name, description, or readme signals.
- **Private repo:** will not appear in the current implementation because the app does not search the user's private repo inventory.
- **User-owned repo:** not specially boosted today. It may appear only because it matches the search query.

### What would be needed to guarantee user repos appear

- A connected GitHub account feature
- A `/user/repos` ingestion path
- Optional boosting for user-owned repos

## 13. What is not implemented yet

The current code does **not** implement:

- connected GitHub account ingestion
- private GitHub repo search or private repo boosting
- user-owned repo prioritization
- Google reviews-based ranking
- official Udemy API integration
- official Coursera partner API integration
- manual human curation override for discovery ranking
- click-through / conversion analytics for learning suggestions
- explicit "why this result" explanations per card
- repo-quality scoring beyond stars/template/recency signals
- a first-class GitHub `/user/repos` sync pipeline

## 14. Recommended next improvements

These are product recommendations, not current behavior:

1. Connect GitHub accounts so user-owned repos can be indexed intentionally.
2. Add private-repo ingestion only with explicit permission.
3. Boost user-owned repos when they genuinely match a missing skill.
4. Detect proof projects inside the user's own repos.
5. Match repo README, topics, language, and recent commit activity to job gaps.
6. Add a richer repository quality score:
   - README present
   - recent commits
   - tests present
   - deployed link
   - stars
   - topics
7. Add learning-resource feedback actions:
   - helpful / not helpful
   - completed
   - save for later
8. Add manual/admin curation overrides.
9. Add explicit provider fallback ordering when one provider is unavailable.
10. Show a transparent "Why this result?" explanation on every card.

## 15. Quick answers

### GitHub repo search algorithm summary

CareerOS uses the GitHub Search API to find public repositories that match the normalized skill. It queries both template-style and project-style patterns, excludes forks and archived repos, then ranks by stars with bonuses for template/starter-like signals and recency.

### GitHub issue search algorithm summary

CareerOS uses the GitHub Search API to find open issues labeled `good first issue` or `help wanted`, skips pull requests, and ranks issues by GitHub search score plus label bonuses.

### Web search algorithm summary

CareerOS uses a configured web search backend (`bing`, `tavily`, or `serpapi`) to find trusted learning resources on approved domains. Results are verified by URL, filtered for relevance and free-signals, then ranked internally by trust, relevance, freshness, and verification time.

### YouTube algorithm summary

CareerOS uses the official YouTube Data API v3, searches for `"{skill_name} free tutorial"`, fetches video details, filters to trusted channels, and stores verified video resources with internal trust/relevance/freshness scores.

### Current ranking factors

- Skill match / normalized skill name
- GitHub stars for repository discovery
- Template/starter-like repo signals
- GitHub issue labels (`good first issue`, `help wanted`)
- Trust score for learning resources
- Relevance score for learning resources
- Freshness / recency
- Verified URL / verification status
- Free vs paid / unknown status

### Whether the user's own repos can appear

Yes, if they are public and match the public GitHub search query. They are not specially prioritized today.

### Whether private repos can appear

No, not in the current implementation.

### Whether Google reviews/stars affect ranking

No. Google reviews are not used. GitHub stars matter only for GitHub repository discovery.

