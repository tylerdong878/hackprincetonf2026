# Grain of Salt: Research Notes

Facts we can use in the pitch and Devpost, plus the technical constraints that affect the build.
Each claim has a source. **Read the "careful" notes before putting anything on a slide.**

---

## 1. Pitch facts

### 1.1 New Jersey requires this, and the standards are still landing
- **The law:** Gov. Murphy signed **S-588** on Jan 4, 2023 (P.L.2022, c.138). NJ became the **first state to require K-12 information literacy**. Illinois already required it for high school only. ([NJ Monthly](https://njmonthly.com/articles/news/new-jersey-becomes-first-state-to-require-k-12-information-literacy), [NJPSA](https://njpsa.org/governor-signs-information-literacy-bill-into-law/))
- **Where it lands:** information-literacy expectations go into the **NJ Student Learning Standards for Career Readiness, Life Literacies, and Key Skills (NJSLS-CLKS)**.
  - A Nov 2025 State Board presentation anticipated adoption in spring 2026. ([NJ DOE, Nov 2025](https://www.nj.gov/education/sboe/meetings/agenda/2025/November/public/5f6_NJSLS_CLKS_and_Science_presentation.pdf))
  - A mid-2026 NJSBA note said public comment on the draft revisions stayed open through **July 31, 2026**. ([NJSBA](https://www.njsba.org/news-information/school-board-notes/state-board-of-education-adopts-science-standards-for-2026-2027-and-recognizes-lighthouse-awardees-at-june-meeting/))
- **The rules already in force:** the State Board readopted N.J.A.C. 6A:8 on Oct 8, 2025, which requires districts to offer information-literacy instruction. ([NJ DOE](https://nj.gov/education/sboe/meetings/agenda/2025/October/public/5c1_Item_C_Standards_and_Assessment.pdf))
- **Pitch line:** *"New Jersey requires every K-12 student to learn this, and the new state standards are being finalized right now. Teachers need tools."*
- ⚠️ **Careful:** final adoption of the CLKS revisions is **unconfirmed**. Don't say "the standards took effect." Say "being finalized."

### 1.2 The research twist: earlier games made people doubt everything
- **The study:** Modirrousta-Galian & Higham (2023), *Journal of Experimental Psychology: General*. They reanalyzed 5 earlier studies of the *Bad News* and *Go Viral!* games with signal-detection (ROC) methods.
  - When true and fake items were comparable, the games **did not improve discrimination**. They made players answer "false" to **everything**.
  - The authors say these interventions "are not as effective as previously thought and may even be counterproductive."
  - Sources: [PubMed](https://pubmed.ncbi.nlm.nih.gov/36996156/), [accepted manuscript](https://eprints.soton.ac.uk/475360/2/2023_JEPG_Accepted_Manuscript.pdf), [SSRC MediaWell summary](https://mediawell.ssrc.org/?p=77299).
- **Replications agree:**
  - An independent study (Lindsay's group) found *Bad News* increased response bias without improving discrimination.
  - A 2026 *Psychonomic Bulletin & Review* brief report found no improved discrimination for Indian headlines. ([UCL](https://discovery.ucl.ac.uk/id/eprint/10211973/7/Modirrousta-Galian_s13423-025-02827-x.pdf))
- **Bonus support:** the same researchers' *inductive learning* intervention (learning from labeled true and false examples with feedback) **did** improve discrimination in three preregistered experiments. Our design (real and doctored examples, feedback on both kinds of mistake) is closer to that approach.
- **Pitch line:** *"Earlier games taught people to doubt everything. Grain of Salt scores whether you can tell the difference."*
- ⚠️ **Careful:**
  - Don't claim Grain of Salt *is proven* to work. Say "it's designed around what the research found, and it measures discernment so it can be tested."
  - Older *Bad News* studies reported benefits. Frame it as "a reanalysis found," not "Bad News doesn't work."

### 1.3 Students struggle, and it's teachable fast
- **Stanford History Education Group, 2019** ("Students' Civic Online Reasoning: A National Portrait"):
  - **3,446 high school students** in 16 districts across 14 states.
  - **90% got no credit on four of the six tasks.**
  - On a video claiming voter fraud, **only 3 of more than 3,000 students tracked down the original source.**
  - Sources: [Stanford](https://purl.stanford.edu/cz440cm8408), [EdWeek](https://www.edweek.org/teaching-learning/students-are-really-really-bad-at-spotting-fake-news-misleading-websites/2019/11).
  - ⚠️ **Careful:** the sample isn't strictly nationally representative, and the data is from 2019.
- **Lateral reading works quickly:** Wineburg et al. (2022), *Journal of Educational Psychology* 114(5), a randomized experiment with **499 high school students**.
  - **Fewer than 6 hours** of lateral-reading lessons significantly improved students' judgments of online credibility.
  - Sources: [Stanford](https://ed.stanford.edu/news/it-doesn-t-take-long-learn-how-spot-misinformation-online-stanford-study-finds), [Edutopia](https://www.edutopia.org/article/what-fact-checkers-know-about-media-literacy-and-students-should-too/).
  - ⚠️ **Careful:** outlets report the effect size differently ("twice as well," "+71%"). Say "significantly improved in under six hours."

### 1.4 Why our tricks: real material in the wrong context is the most common kind
- **AMMeBa** (Dufour et al., 2024, Google researchers): human raters annotated media-based misinformation drawn from **135,838 fact-checked claims** (1995–Nov 2023).
  - About **80% involve media**.
  - **The most common type is context manipulation: real, unaltered images paired with false claims.** Generative-AI fakes rose only recently.
  - Sources: [arXiv](https://arxiv.org/abs/2405.11697), [Hugging Face](https://huggingface.co/papers/2405.11697).
- **Pitch line:** *"Most misinformation isn't deepfakes. It's real stuff, out of context. That's what we train."*
- **Charts fool people, even after a warning:** Yang, Restrepo & Stanley (2021), *Journal of Applied Research in Memory and Cognition*.
  - Across 5 studies, **83.5% of participants** were fooled by truncated y-axes.
  - The effect **persisted even after people were taught about truncation**. Quantitative PhD students were only slightly more resistant.
  - Correll et al. (CHI 2020) found that flagging a truncated axis didn't remove the effect.
  - Sources: [paper PDF](https://www.Gwern.net/doc/psychology/cognitive-bias/2021-yang-4.pdf), [Tableau Research](https://www.tableau.com/blog/truncating-y-axis-threat-or-menace).
  - **This supports practice over warnings.**
  - ⚠️ **Careful:** some line-chart studies found smaller effects. Keep the claim to bar charts.

### 1.5 Young people get their news from feeds
- **43% of 18–29-year-olds regularly get news on TikTok** (Pew 2025), up from 9% in 2020. ([Pew](https://www.pewresearch.org/topic/platforms-services))
- **68% of US teens (13–17) use TikTok**, and about 1 in 5 are on a major platform "almost constantly" (Pew survey of 1,458 teens, Sept–Oct 2025). ([Pew](https://www.pewresearch.org/2025/12/09/teens-social-media-and-ai-chatbots-2025/))
- ⚠️ **Careful:** we didn't find a single "% of teens who get news on TikTok" number. Use the 18–29 figure or the teen usage figure.

### 1.6 Prior art (know these before a judge asks)

| Thing | What it is | How we're different |
|---|---|---|
| **Bad News / Go Viral! / Harmony Square** (Cambridge + DROG) | Scripted games where you play the fake-news producer | Fixed content. The reanalysis shows blanket suspicion. Ours uses fresh cases from real news, scores discernment, and adapts per trick. |
| **Checkology** (News Literacy Project) | The leading classroom platform: 22,800+ educators, 890,000+ students, 6,000+ districts in 2025–26 (self-reported) ([NLP](https://newslit.org/our-impact/)) | Lessons and modules. Ours is a daily, replayable, adaptive game. **This also proves teachers will adopt a tool like this.** |
| **Breaking the News** (research, about 2024) | An LLM game where players act as influencer or debunker; 47-person study ([ResearchGate](https://www.researchgate.net/publication/388848236_Breaking_the_News_A_LLM-based_Game_where_Players_Act_as_Influencer_or_Debunker_for_Raising_Awareness_About_Misinformation)) | Opinion simulation. Ours builds verifiable cases from real material and measures discernment. |
| **AI-NPC digital literacy game** (MDPI, Jan 2026) | LLM-driven characters in a misinformation scenario ([MDPI](https://www.mdpi.com/2227-9709/13/1/16)) | No per-player adaptation of tricks, no blind-solver validation. |
| **A Mystery for You** (CHI 2024) | An LLM-enhanced fact-checking game with a tangible interface, for kids ([ACM](https://dl.acm.org/doi/10.1145/3613905.3648110)) | A physical, story-driven format. Ours is a daily online case bank. |

**The gap we fill**, based on what the searches turned up: no shipped tool we found **adapts the manipulation techniques to each learner's weaknesses while scoring both misses and false alarms**.

---

## 2. OpenRouter free tier (affects the build)
Sources: [limits](https://openrouter.ai/docs/api-reference/limits), [FAQ](https://openrouter.ai/docs/faq), [free models](https://openrouter.ai/collections/free-models), [quickstart](https://openrouter.ai/docs/quickstart).

**Rate limits:**
- Free (`:free`) models: **20 requests/minute** for everyone.
- **50 requests/day** if the account has bought **less than $10** of credits, all-time.
- **1,000 requests/day** once the account has bought **$10 or more** of credits. One page says $9; check with `GET /api/v1/key`.
- **Failed requests count** toward the daily cap.

**Models:**

| Use | Slug | Tools | Images |
|---|---|---|---|
| Orchestrator / forger | `nvidia/nemotron-3-ultra-550b-a55b:free` | Yes | Not stated |
| Blind solver (reads charts) | `nvidia/nemotron-3.5-super-vl:free` | Yes | **Yes** |
| Small tasks | `nvidia/nemotron-3.5-lightning:free` | Yes | Not stated |
| Backup main model | `thinkingmachines/inkling-2-small:free` | Yes | Yes |

**Calling the API:**
- Base URL: `https://openrouter.ai/api/v1`
- Header: `Authorization: Bearer <OPENROUTER_API_KEY>`
- Optional headers: `HTTP-Referer` and `X-OpenRouter-Title`
- Use the `:free` slug. The slug without `:free` is the paid version.

**Privacy:**
- Prompts aren't logged by default.
- Providers that log are skipped unless you enable training/logging in your privacy settings. If a free model returns "no endpoints," check that setting.

**What 50 a day means for us:**
- Building one case can take dozens of calls (orchestrator turns, sub-agents, solver retries).
- 50 a day covers roughly 1–2 cases **per account**, and development testing burns through that fast.

**Options, in order:**
1. Develop against a local or free model (Ollama, the Gemini free tier, Groq). Save OpenRouter for generating the final cases.
2. Each teammate makes an account, which gives 4 × 50 a day.
3. *If the team agrees:* one person buys $10 of credits once, which raises the cap to 1,000 a day. It's the only paid option, and it's optional.

**Either way, generate the 5 demo cases by Saturday evening.** The demo plays saved cases, so judging uses zero API calls.

---

## 3. Deep Agents details
Current release: **`deepagents` 0.7.38** (Nov 13, 2026). The workshop repo pins `>=0.7`.
Sources:
- [overview](https://docs.langchain.com/oss/python/deepagents/overview)
- [sub-agents](https://docs.langchain.com/oss/python/deepagents/subagents)
- [skills](https://docs.langchain.com/oss/python/deepagents/skills)
- [backends](https://docs.langchain.com/oss/python/deepagents/backends)
- [human-in-the-loop](https://docs.langchain.com/oss/python/deepagents/human-in-the-loop)
- [event streaming](https://docs.langchain.com/oss/python/deepagents/event-streaming)
- [models](https://docs.langchain.com/oss/python/deepagents/models)
- [CHANGELOG](https://github.com/langchain-ai/deepagents/blob/main/libs/deepagents/CHANGELOG.md)
- [workshop repo](https://github.com/langchain-samples/hack-princeton-intro-to-deep-agents)

### 3.1 Gotchas that will bite us (breaking changes in 0.7)
- **Todos are off by default.** Pass `middleware=[TodoListMiddleware()]`, or the Workshop panel has no plan to show. Sub-agents don't inherit custom middleware, so add it to each sub-agent that needs todos.
- **The default system prompt is now empty.** Write a full `system_prompt` for the orchestrator.
- **`FilesystemBackend` defaults to `virtual_mode=True`**, and `root_dir` must be an **absolute** path. Pass both explicitly. The backends doc page still says the opposite.
- **`write_file` overwrites existing files.**
- **Always pass `model`.** The no-model fallback is deprecated.
- **Refusals raise an error:** since 0.7.33, a refusal raises `ModelRefusalError`. Catch it in the pipeline and retry with a reworded request or the backup model.
- **The workshop repo calls Anthropic directly:** `utils/models.py` and the `web_research` tool in `utils/search.py`. Replace both.

### 3.2 The model: use the dedicated OpenRouter integration
```python
# pip install "langchain-openrouter>=0.2.0"   (latest 0.2.9)
from langchain_openrouter import ChatOpenRouter   # verify import path when installing

orchestrator_model = ChatOpenRouter(
    model="nvidia/nemotron-3-ultra-550b-a55b:free",
    openrouter_provider={"require_parameters": True},  # skip providers lacking tool support
)  # reads OPENROUTER_API_KEY
solver_model = ChatOpenRouter(model="nvidia/nemotron-3.5-super-vl:free",
                              openrouter_provider={"require_parameters": True})
```
- The docs warn that plain `ChatOpenAI(base_url=...)` only covers "basic chat" and can drop provider-specific fields like reasoning content. **Prefer `ChatOpenRouter`.**
- Don't use the `openai:` model string, which defaults to the Responses API.
- ⚠️ **No free models are in Deep Agents' model evaluations.** The top OpenRouter scores went to paid models: GLM 5.1 (89%), DeepSeek V4 Flash (81%), MiniMax M2.7 (80%). **Test tool-calling reliability with Nemotron tonight.** If it struggles, try Inkling 2 Small, then Gemini's free tier.

### 3.3 Sketch for our pipeline
```python
from deepagents import create_deep_agent
from deepagents.backends import CompositeBackend, StateBackend, FilesystemBackend
from langchain.agents.middleware import TodoListMiddleware   # verify import path
from langgraph.checkpoint.memory import MemorySaver

ROOT = r"C:\...\hackprincetonf2026\data"   # absolute path
# Each route needs its OWN backend: CompositeBackend strips the route prefix, so one backend at data/
# would read /cases/x as data/x. (Corrected after building the pipeline; see pipeline/agent.py.)
backend = CompositeBackend(
    default=StateBackend(),                 # scratch stays in state
    routes={
        "/cases/":  FilesystemBackend(root_dir=ROOT + r"\cases",  virtual_mode=True),
        "/skills/": FilesystemBackend(root_dir=ROOT + r"\skills", virtual_mode=True),
    },
)

researcher = {"name": "researcher", "description": "Collect verbatim real sources with URLs for one topic.",
              "system_prompt": RESEARCHER_PROMPT, "tools": [fetch_rss, fetch_article, fetch_open_data, save_source],
              "model": orchestrator_model}
forger     = {"name": "forger", "description": "Apply one trick skill to real material and write case + answer key.",
              "system_prompt": FORGER_PROMPT, "tools": [crop_quote, make_chart_spec, make_stat_claim],
              "skills": ["/skills/"], "model": orchestrator_model}
solver     = {"name": "blind-solver", "description": "Solve a case WITHOUT the answer key using only the evidence kit.",
              "system_prompt": SOLVER_PROMPT, "tools": [open_evidence, view_chart_png],
              "model": solver_model}

agent = create_deep_agent(
    model=orchestrator_model,
    system_prompt=ORCHESTRATOR_PROMPT,
    tools=[submit_for_review],              # custom tool; gating it = the teacher-approval pause
    subagents=[researcher, forger, solver],
    middleware=[TodoListMiddleware()],
    backend=backend,
    interrupt_on={"submit_for_review": {"allowed_decisions": ["approve", "edit", "reject"]}},
    checkpointer=MemorySaver(),             # required for interrupts (omit under `langgraph dev`)
)
```

**Sub-agents:**
- Fields: `name`, `description`, `system_prompt` (required); `tools`, `model`, `middleware`, `interrupt_on`, `skills`, `response_format`, `permissions` (optional).
- A sub-agent's `tools` **replace** inherited tools entirely.
- The orchestrator calls them through the built-in `task` tool (`subagent_type`, `description`).

**Skills:**
- The layout is `/skills/<name>/SKILL.md`.
- Frontmatter needs `name`, which must **match the folder name** (lowercase-hyphen, 64 characters max), and `description` (1,024 characters max).
- Only the name and description go into the prompt. The body is read on demand.
- `skills=[...]` must point at the **folder that contains skill folders**.
- Sub-agents don't inherit skills, so give the forger `"skills"` explicitly.

**Human-in-the-loop (teacher approval):**
- **How the pause works:** `interrupt_on` works on custom tool names, so we gate `submit_for_review`. That's our design choice, not a documented recipe.
- **Reading the pause:** the request is at `result["__interrupt__"][0].value["action_requests"]`.
- **Resuming:** call again with the same `thread_id`, passing `Command(resume={"decisions": [...]})`. The decision is `{"type": "approve"}`, `{"type": "reject", "message": "..."}`, or `{"type": "edit", "edited_action": {"name": ..., "args": {...}}}`.
- **Sub-agents** inherit `interrupt_on` unless they set their own.

### 3.4 Streaming the Workshop panel
- **In-process (simplest for FastAPI → server-sent events):**
  - `agent.stream_events(input, version="v3")`, then iterate `stream.interleave("messages", "subagents")`.
  - Each sub-agent handle has `.name`, `.status`, `.tool_calls`, `.output`.
- **Classic:** `agent.stream(..., stream_mode=["messages", "updates"], subgraphs=True)`.
  - The todos live in the state key `todos`.
  - Interrupts arrive as `"__interrupt__"`.
- **Workshop Module 2 approach:**
  - Run `langgraph dev --port 2024` plus the LangGraph SDK: `client.runs.stream(..., stream_mode="updates", stream_subgraphs=True)`.
  - Events named `"updates|tools:<id>"` are sub-agent activity.
  - A React `useStream` hook reads `stream.values.todos`.
- ⚠️ **Files routed to disk won't appear in state `files`.** Build the file list from `write_file`/`edit_file` tool-call arguments instead.
- **Saving runs for replay:** write every event to `cases/<id>/pipeline_log.jsonl` as it streams. Replay mode reads that file, so the demo needs no API calls.

### 3.5 Player profiles
- Keep them simple: plain JSON in `/players/<id>/profile.json`.
  - The FastAPI game server reads and writes them.
  - The pipeline reads them through the disk route when choosing tricks.
- Deep Agents' `StoreBackend` and long-term memory exist (namespaces by user via `context_schema`), but we don't need them for the minimum version.

## 4. Demo topic and data

### 4.1 Pick: NJ electricity prices
**Backup:** NJ minimum wage (safest, most relatable to teens). **Third choice:** NJ Transit fares and ridership.

**Why electricity:**
- Real monthly data runs through Aug 2026.
- There are fresh real quotes from the regulator (the BPU, NJ's Board of Public Utilities) and from New Jersey Monitor (Sept and Nov 2026).
- The material naturally contains all three tricks:
  - seasonal peaks, which make cherry-picked windows easy
  - a quote that hinges on the word "net"
  - bill changes that offset each other
- Everyone pays a power bill: judges directly, teens through their families.

⚠️ **Careful:** affordability was a campaign issue. Use only regulator (BPU), federal (EIA) and straight-news sources, and skip partisan reports. Don't use campaign framing. The midterms were Nov 3, so the "near voting day" block doesn't apply, but keep it neutral.

**Data (EIA API v2, NJ residential average price, cents per kWh, monthly 2001-01 to 2026-08):**
```
https://api.eia.gov/v2/electricity/retail-sales/data/?api_key=DEMO_KEY&frequency=monthly&data[0]=price&facets[stateid][]=NJ&facets[sectorid][]=RES&sort[0][column]=period&sort[0][direction]=asc&length=5000
```
- Get a free key at [eia.gov/opendata/register.php](https://www.eia.gov/opendata/register.php). `DEMO_KEY` works but is heavily rate-limited.
- **Fetch it once and save it to `data/`.** The game never calls the API live.

| Period | ¢/kWh |
|---|---|
| Feb 2001 (all-time low) | 9.34 |
| Jun 2024 | 19.90 |
| Apr 2025 | 19.91 |
| Jun 2025 | 24.65 |
| Jul 2025 | 25.11 |
| Apr 2026 | 23.53 |
| Jul 2026 | 25.19 |
| Aug 2026 (latest) | 24.61 |
| 2024 annual | 19.34 |
| 2025 annual | 22.48 |

Every summer has a strong peak, which is useful for the cherry-picked-window trick.

### 4.2 The demo case: "Is your power bill really frozen?"
All quotes were reported verbatim from the pages below. **Re-check each against its page before shipping.** The researcher agent re-fetches them anyway.

| # | Role in case | Post |
|---|---|---|
| 1 | **Doctored** (misleading chart, posted by a *made-up* account) | "NJ power prices up 27% in one year!" The chart runs **Apr 2025 (19.91) to Jul 2026 (25.19)** with the y-axis starting at 19. **The tell:** it compares April 2025, *before* the summer 2025 spike, with July 2026, 15 months later, on a cropped axis. The honest same-month change is **Jul 2025 → Jul 2026 = +0.3%**. The big jump happened in summer 2025 (Apr→Apr is +18.2%), and the chart smuggles it into a "one year" window. *(Re-verified Nov 14 against the downloaded EIA data.)* |
| 2 | **Real but sounds fake** | NJBPU, Aug 13, 2026: bills "jumped roughly 20 percent last year." ([BPU](https://nj.gov/bpu/newsroom/2026/approved/20260813.html)) |
| 3 | **Real** (and it seems to contradict post 1, which makes it suspicious) | BPU's Hertz-Shargel, reported by NJ Monitor on Sept 24, 2026: "Taken together with the items on the agenda earlier this month, these actions will result in no net increase in electricity rates and a slight decrease in gas rates." ([NJ Monitor](https://newjerseymonitor.com/2026/09/24/utilities-board-votes-electric-rates/)) *Verify their title.* |
| 4 | **Real** | Commissioner Emma Rebhorn, NJ Monitor, Nov 12, 2026: "it is the most expensive hours of the year that are driving the really unsustainable price hikes in the utility and electricity bills that we saw in the last few years." ([NJ Monitor](https://newjerseymonitor.com/2026/11/12/nj-virtual-power-plant-battery-storage/)) |

**Material for the other 4 cases:**
- **Quote crop:** drop "net", so it reads "...will result in no increase in electricity rates."
- **Missing offset:** Atlantic City Electric bills "will rise by $4.09" from some charges but "will fall by $4.14" from others, "leaving the average monthly bill 5 cents cheaper" (NJ Monitor, 9/24). The doctored post says: "ACE bills rising $4.09 a month."
- **Quote crop:** Rebhorn cut down to "really unsustainable price hikes in the utility and electricity bills."
- **Missing denominator:** capacity charges "account for approximately 15 to 20 percent of a typical customer's electric bill" (BPU, 8/13).
- **Real filler:** "The fastest way to lower bills is getting new power generation built." (Hertz-Shargel, NJ Monitor 9/24)
- **A clean case:** four real items, no doctoring.

### 4.3 Licensing and how we present sources
- **New Jersey Monitor** content is **CC BY-NC-ND 4.0** ([republishing guidelines](https://newjerseymonitor.com/republishing-guidelines/)): attribute, link, and edit only for style or length. **No derivatives.**
- **What we do:**
  - Use short attributed excerpts with a link.
  - **Never present a doctored version as NJ Monitor or BPU content.**
  - Doctored posts always come from made-up accounts.
  - Real posts show the outlet's name in plain text, no logos, with a link.
- This is our reading of the license, not legal advice.

### 4.4 Backups
- **Minimum wage:**
  - FRED CSV, no key needed: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=STTMINWGNJ` (annual 1968–2026). Values: 8.25 (2014), 8.60 (2018), 10.00 (2019), 15.92 (2026).
  - Pair it with CPI for nominal vs. inflation-adjusted views.
  - News: [NJDOL 9/29/2026](https://www.nj.gov/labor/lwdhome/press/2026/20260929_min_wage.shtml). The rate rises "$0.56" to "$16.48" on Jan 1, 2027, and the tipped cash wage goes from $6.05 to $6.61.
- **NJ Transit:**
  - FTA National Transit Database ridership, monthly 2014-01 to 2026-09: `https://data.transportation.gov/resource/5ti2-5uiv.json` (filter `_5_digit_ntd_id='20080'`).
  - Annual totals: 177.5M (2019), 94.4M (2020), 168.0M (2024), 160.9M (2025).
  - News: [NJ Monitor 7/1/2026](https://newjerseymonitor.com/2026/07/01/nj-transit-fares-increase/) (fares "rising 3% systemwide").
- **Rejected:**
  - Rents: the Census API now needs a key, and rent indexes disagree.
  - Tolls and beach badges: no dataset.
  - Gas prices: EIA doesn't break out NJ.

### 4.5 Free news feeds (tested Nov 13, 2026)

| Outlet | Feed | Notes |
|---|---|---|
| New Jersey Monitor | `https://newjerseymonitor.com/feed/` | 100 items, **full article text**. Best source. |
| NJ Spotlight News | `https://www.njspotlightnews.org/feed/` | 10 items |
| NJ.com | `https://www.nj.com/arc/outboundfeeds/rss/?outputType=xml` | Mostly sports and deals |
| WHYY (NJ tag) | `https://whyy.org/tag/new-jersey/feed/` | Works |
| NJ 101.5 | `https://nj1015.com/feed/` | 35 items |
| Patch (Princeton) | `https://patch.com/feeds/aol/new-jersey/princeton` | Per town only |
| NPR / BBC | `https://feeds.npr.org/1001/rss.xml` · `https://feeds.bbci.co.uk/news/rss.xml` | General |
| NorthJersey.com | Not working | 402/404 errors |
