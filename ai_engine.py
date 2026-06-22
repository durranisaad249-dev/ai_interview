"""
ai_engine.py — InterviewAI Pro v3.4
Deep, field-specific question generation for 5 roles.
Each role has its own expert-level prompt strategy.
"""
import os, json, io, requests
from dotenv import load_dotenv

load_dotenv()

OLLAMA_BASE  = "http://localhost:11434"
OLLAMA_URL   = os.getenv("OLLAMA_URL",   f"{OLLAMA_BASE}/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "")   # empty = auto-detect

# ── Auto-detect which model is available ──────────────────────────
_detected_model = None

def _get_model() -> str:
    """
    Return the model to use.
    Priority: env var → cached detection → first installed model → error.
    """
    global _detected_model

    # 1. Use .env model if set and not empty
    env_model = os.getenv("OLLAMA_MODEL", "").strip()
    if env_model:
        return env_model

    # 2. Return cached detection
    if _detected_model:
        return _detected_model

    # 3. Ask Ollama which models are installed
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        if r.ok:
            models = r.json().get("models", [])
            if models:
                # Prefer common chat models
                names = [m.get("name","") for m in models]
                preferred = ["llama3","llama3.2","llama3.1","mistral",
                             "llama2","phi3","phi","gemma","qwen","deepseek"]
                for pref in preferred:
                    for n in names:
                        if pref in n.lower():
                            _detected_model = n
                            return _detected_model
                # Fallback: just use first one
                _detected_model = names[0]
                return _detected_model
    except Exception:
        pass

    raise ConnectionError(
        "No Ollama model found.\n"
        "Fix: open Terminal → run:  ollama pull llama3.2\n"
        "Then retry."
    )

# ── Ollama call ────────────────────────────────────────────────────
def _ask(prompt: str, temp: float = 0.7, tokens: int = 1800) -> str:
    try:
        model = _get_model()
    except ConnectionError as e:
        raise e

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": temp, "num_predict": tokens}
    }

    try:
        r = requests.post(OLLAMA_URL, json=payload, timeout=180)
    except requests.exceptions.ConnectionError:
        raise ConnectionError(
            "Ollama is not running.\n"
            "Fix: open Terminal → run:  ollama serve"
        )
    except requests.exceptions.Timeout:
        raise TimeoutError(
            "Ollama timed out (180s).\n"
            "Try a smaller model:  ollama pull phi3"
        )

    # Handle 404 = model doesn't exist on this machine
    if r.status_code == 404:
        global _detected_model
        _detected_model = None   # clear cache, force re-detect next time
        raise ConnectionError(
            f"Model '{model}' not found in Ollama.\n\n"
            "Fix — run ONE of these in Terminal:\n"
            "  ollama pull llama3.2   (recommended, ~2GB)\n"
            "  ollama pull mistral    (~4GB)\n"
            "  ollama pull phi3       (small, fast, ~2GB)\n\n"
            "Then refresh the page."
        )

    try:
        r.raise_for_status()
    except Exception as e:
        raise ConnectionError(f"Ollama error {r.status_code}: {r.text[:200]}")

    return r.json().get("response", "").strip()

def _parse_json(raw: str):
    text = raw.strip()
    if "```" in text:
        for p in text.split("```"):
            p = p.strip().lstrip("json").strip()
            if p.startswith("[") or p.startswith("{"):
                text = p; break
    for s, e in [("[", "]"), ("{", "}")]:
        si = text.find(s)
        if si != -1:
            ei = text.rfind(e)
            if ei != -1:
                try: return json.loads(text[si:ei+1])
                except: pass
    raise ValueError("No JSON found")

def check_ollama_status() -> dict:
    """Return online status + which model will be used."""
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=3)
        if not r.ok:
            return {"online": False, "model": ""}
        models = r.json().get("models", [])
        names  = [m.get("name","") for m in models]
        try:
            model = _get_model()
        except Exception:
            model = names[0] if names else ""
        return {"online": True, "model": model, "all_models": names}
    except Exception:
        return {"online": False, "model": "", "all_models": []}


# ════════════════════════════════════════════════════════════════════
#  DEEP ROLE STRATEGIES
#  Each entry defines exactly what depth of questions to generate.
# ════════════════════════════════════════════════════════════════════
DEEP_STRATEGIES = {

    "Software Engineering": {
        "depth_instruction": """
You are a Principal Engineer at Google/Meta conducting a SENIOR-level technical interview.
Generate DEEP, complex questions that go beyond surface knowledge. Focus on:

TECHNICAL DEPTH AREAS:
- System Design: distributed systems, CAP theorem, consistency models, event-driven architecture,
  CQRS, saga pattern, distributed transactions, leader election, consensus algorithms (Raft/Paxos)
- Data Structures & Algorithms: time/space complexity analysis, when to use what and WHY,
  graph algorithms, dynamic programming, segment trees in production contexts
- Concurrency: race conditions, deadlocks, lock-free data structures, memory models,
  actor model vs shared memory, async/await internals
- Database Engineering: query optimization, indexing strategies (B-tree vs hash vs composite),
  ACID vs BASE, isolation levels, N+1 problem, connection pooling, sharding vs partitioning
- Architecture: monolith vs microservices trade-offs, API gateway patterns, service mesh,
  circuit breakers, bulkhead pattern, back-pressure, event sourcing
- Security: OWASP Top 10 in depth, SQL injection prevention at DB level, JWT internals,
  OAuth 2.0 flows, PKCE, supply chain attacks, secrets management
- Reliability: SLOs/SLAs/error budgets, chaos engineering, observability (traces/metrics/logs),
  graceful degradation, blue-green vs canary deployments
- Code Quality: SOLID principles with real trade-offs, DDD, hexagonal architecture,
  technical debt quantification, code review best practices
""",
        "behavioral_areas": """
- Leading a team through a major architectural refactor under time pressure
- Disagreeing with a senior engineer's technical decision and the outcome
- Debugging a production incident with cascading failures at 3am
- Mentoring a junior developer who repeatedly makes the same mistakes
- Making a build vs buy decision for a critical system component
"""
    },

    "Data Science": {
        "depth_instruction": """
You are a Senior Data Scientist at a top-tier AI research lab conducting an expert interview.
Generate DEEP, complex questions that test real practitioner knowledge. Focus on:

TECHNICAL DEPTH AREAS:
- Statistics & Math: deriving gradient descent from first principles, Bayesian vs frequentist
  trade-offs, maximum likelihood estimation, hypothesis testing (power analysis, p-value pitfalls),
  covariance matrices, PCA derivation, Lagrange multipliers in SVM
- Machine Learning Theory: bias-variance decomposition mathematically, PAC learning,
  VC dimension, kernel trick internals, attention mechanism math, backpropagation through time,
  vanishing/exploding gradients — causes and solutions beyond just clip/LR
- Model Selection & Evaluation: calibration curves, expected calibration error,
  multi-label metrics (macro vs micro vs weighted F1), imbalanced dataset strategies
  beyond SMOTE, stratified k-fold edge cases, data leakage detection
- Feature Engineering: target encoding and leakage risks, high-cardinality categoricals,
  time-series feature engineering (lag features, rolling statistics, seasonality decomposition),
  feature interaction detection
- MLOps & Production: model drift detection (PSI, KL divergence), shadow deployment,
  champion-challenger patterns, online learning trade-offs, feature store design,
  model versioning strategies, AB test statistical power for ML metrics
- Deep Learning: transformer architecture internals (multi-head attention math),
  normalisation layers (batch vs layer vs group norm — when each), regularisation
  (dropout, label smoothing, mixup, cutmix), training stability techniques
- Experiment Design: confounding variables, Simpson's paradox in real data,
  Bayesian AB testing vs frequentist, multi-armed bandit vs AB test
""",
        "behavioral_areas": """
- Presenting a model that performed great offline but failed in production — root cause analysis
- Stakeholder wanted a simple model vs your recommendation for a complex one
- Discovering data leakage after model was already deployed to production
- Disagreeing with a business decision based on your data analysis findings
- Building a DS function/team from scratch with no existing infrastructure
"""
    },

    "Frontend Engineering": {
        "depth_instruction": """
You are a Staff Frontend Engineer at Netflix/Airbnb conducting a senior technical interview.
Generate DEEP, expert-level questions. Focus on:

TECHNICAL DEPTH AREAS:
- Browser Internals: rendering pipeline in detail (parse → style → layout → paint → composite),
  reflow vs repaint triggers, layer promotion heuristics, JavaScript event loop,
  microtasks vs macrotasks vs animation frames, V8 JIT compilation and deoptimisation
- JavaScript Internals: prototype chain mechanics, closure memory implications,
  WeakRef and FinalizationRegistry, generator functions and async iterators,
  Proxy and Reflect internals, module evaluation order, tree shaking at bundler level
- React/Framework Depth: reconciliation algorithm (Fiber architecture), concurrent mode and
  Suspense internals, useEffect cleanup timing, stale closure bugs patterns,
  React Server Components trade-offs, hydration mismatch errors, render batching
- Web Performance: Core Web Vitals internals (LCP attribution, INP measurement, CLS shifts),
  critical rendering path optimisation, resource hints (preload vs prefetch vs preconnect),
  HTTP/2 multiplexing impact on bundle splitting strategy, image format trade-offs (AVIF/WebP),
  service worker caching strategies (stale-while-revalidate, cache-first)
- State Management: Redux vs Zustand vs Jotai architectural differences, derived state pitfalls,
  normalised vs denormalised store trade-offs, optimistic updates with rollback
- Security: XSS attack vectors (DOM-based vs reflected vs stored), CSP policy design,
  CSRF tokens vs SameSite cookies, prototype pollution attacks, dependency supply chain risks
- Accessibility: ARIA roles and when NOT to use them, focus management in SPAs,
  keyboard trap prevention, colour contrast ratios (WCAG 2.1 AA vs AAA), screen reader
  announcement patterns, skip navigation implementation
- CSS Architecture: specificity wars in large codebases, CSS Houdini APIs,
  container queries vs media queries, CSS custom properties performance,
  critical CSS extraction strategies, CSS-in-JS SSR trade-offs
""",
        "behavioral_areas": """
- Rebuilding a legacy jQuery codebase to React while keeping the product running
- A performance regression you introduced that affected millions of users
- Disagreeing with UX design decisions on accessibility grounds
- Mentoring backend engineers learning frontend — what you changed in your approach
- Choosing between building a micro-frontend architecture vs a monolith
"""
    },

    "Backend Engineering": {
        "depth_instruction": """
You are a Distinguished Engineer at Amazon/Stripe conducting a senior backend interview.
Generate DEEP, expert-level questions. Focus on:

TECHNICAL DEPTH AREAS:
- Distributed Systems: two-phase commit vs saga pattern trade-offs, idempotency key design,
  exactly-once delivery impossibility — how systems approximate it, vector clocks vs Lamport timestamps,
  consistent hashing with virtual nodes, gossip protocols, Phi accrual failure detector
- Database Engineering: WAL (Write-Ahead Log) internals, MVCC implementation across databases,
  index design for range queries vs equality queries, covering index vs index-only scans,
  PostgreSQL query planner hints, write amplification in LSM trees vs B-trees,
  connection pooling (PgBouncer modes: session vs transaction vs statement),
  database-per-service vs shared database trade-offs with real scenarios
- Caching Architecture: cache stampede prevention (probabilistic early expiration, mutex lock),
  cache aside vs read-through vs write-through vs write-behind,
  Redis data structures for specific use cases (HyperLogLog, sorted sets for leaderboards),
  cache eviction policies and when each applies, multilevel caching design
- API Design: REST resource modelling for complex domains, GraphQL N+1 and DataLoader,
  gRPC streaming patterns, API versioning strategies (URL vs header vs content negotiation),
  rate limiting algorithms (token bucket vs sliding window vs leaky bucket internals),
  webhook reliability patterns (retry with exponential backoff, idempotency)
- Message Systems: Kafka partition strategy and consumer group rebalancing,
  at-least-once vs at-most-once vs exactly-once in Kafka, outbox pattern for transactional messaging,
  dead letter queues design, event schema evolution with backward compatibility
- Security: OAuth 2.0 flows in depth (when auth code + PKCE vs client credentials),
  JWT vs session token security trade-offs, SQL injection at ORM level,
  secrets rotation without downtime, mTLS for service-to-service auth
- Reliability Engineering: SLO design and error budget policies, structured logging for
  debuggability, distributed tracing context propagation, circuit breaker state machine,
  bulkhead isolation patterns, load shedding vs backpressure strategies
- Performance: profiling CPU vs memory vs I/O bottlenecks, async vs threading models
  (event loop vs thread pool trade-offs), connection keep-alive optimisation, HTTP/2 server push
""",
        "behavioral_areas": """
- Designing a system that needed to scale from 1k to 10M users — decisions you made
- A production database migration with zero downtime for a critical system
- Debugging an intermittent distributed system issue that only appeared under load
- Choosing between rebuilding vs refactoring a legacy service with tech debt
- A time you pushed back on a product requirement due to technical infeasibility
"""
    },

    "HR Management": {
        "depth_instruction": """
You are a Chief People Officer at a Fortune 500 company conducting a senior HR interview.
Generate DEEP, strategic questions that go beyond basic HR knowledge. Focus on:

STRATEGIC DEPTH AREAS:
- Strategic Workforce Planning: workforce demand forecasting models, skills gap analysis
  methodology, build vs buy vs borrow vs bot talent decisions, workforce segmentation strategy,
  succession planning for critical roles, talent pipeline ROI measurement
- Organisational Design: span of control optimisation, matrix vs hierarchical vs flat structure
  trade-offs in different growth stages, job architecture design (job families, grades, levelling),
  organisational redesign while maintaining productivity, managing redundancies legally and ethically
- Compensation & Total Rewards: compensation benchmarking methodology (Radford, Mercer, Korn Ferry),
  pay equity analysis (regression-based), executive compensation design, equity compensation
  (RSU vs options — dilution implications), variable pay plan design and unintended incentive effects,
  global compensation strategy for remote teams
- Performance Management: designing performance review systems that reduce bias (calibration sessions,
  forced ranking debate, OKR vs KPI alignment), distinguishing high performance from high potential,
  managing underperformers through PIP legally and constructively, performance data analytics
- Employment Law & Compliance: GDPR implications for HR data, wrongful termination risk mitigation,
  protected class discrimination — unconscious bias in hiring processes, non-compete enforceability,
  contractor vs employee misclassification risk, FMLA/ADA accommodation process
- Talent Acquisition: structured interview design (behavioural vs situational vs work sample),
  reducing interviewer bias (blind resume review, diverse panels), employer branding ROI,
  offer acceptance rate optimisation, time-to-fill vs quality-of-hire metrics trade-offs
- Culture & Engagement: measuring psychological safety quantitatively, engagement survey design
  (action planning that drives change vs survey fatigue), DEI metrics that matter (representation
  vs inclusion vs equity), culture integration post-merger/acquisition
- HR Analytics & People Data: predictive attrition models and ethical use, HR dashboard design
  for CHRO vs business leaders, A/B testing HR interventions, HRIS data quality management
- Change Management: ADKAR vs Kotter — when each applies, stakeholder mapping for HR transformations,
  resistance management strategies, measuring change adoption, communication planning
""",
        "behavioral_areas": """
- Leading a large-scale redundancy/restructuring while maintaining culture and morale
- Handling an executive performance issue that the CEO was reluctant to address
- Designing a compensation system from scratch for a hyper-growth startup
- Navigating a discrimination complaint that involved a high-performing senior leader
- Building HR infrastructure and team for a company scaling from 50 to 500 people
"""
    },
}

# ════════════════════════════════════════════════════════════════════
#  RESUME ANALYSIS
# ════════════════════════════════════════════════════════════════════
def analyze_resume(resume_text: str) -> dict:
    prompt = f"""Analyse this resume carefully and extract detailed structured information.

RESUME:
{resume_text[:3500]}

Return ONLY a valid JSON object with these exact fields:
{{
    "name": "<full name or 'Candidate'>",
    "last_role": "<most recent job title>",
    "suggested_role": "<best matching role from: Software Engineering, Data Science, Frontend Engineering, Backend Engineering, HR Management>",
    "field": "<professional field e.g. Software Engineering, HR, Data Science>",
    "experience_years": <integer years of experience>,
    "education": "<highest degree, field, university>",
    "skills": ["skill1","skill2","skill3","skill4","skill5","skill6","skill7","skill8"],
    "technologies": ["tech1","tech2","tech3","tech4","tech5","tech6"],
    "companies": ["company1","company2","company3"],
    "projects": ["project description 1","project description 2","project description 3"],
    "key_achievements": ["achievement1","achievement2","achievement3"],
    "summary": "<2-3 sentence professional summary based on resume>",
    "specialisations": ["area1","area2","area3"]
}}
JSON:"""
    try:
        raw = _ask(prompt, 0.2, 800)
        r = _parse_json(raw)
        defaults = {"name":"Candidate","last_role":"Professional","suggested_role":"Software Engineering",
                    "field":"Technology","experience_years":0,"education":"N/A","skills":[],
                    "technologies":[],"companies":[],"projects":[],"key_achievements":[],
                    "summary":"Experienced professional.","specialisations":[]}
        for k, v in defaults.items():
            r.setdefault(k, v)
        return r
    except Exception:
        return {"name":"Candidate","last_role":"Professional","suggested_role":"Software Engineering",
                "field":"Technology","experience_years":0,"education":"N/A","skills":[],
                "technologies":[],"companies":[],"projects":[],"key_achievements":[],
                "summary":"Professional background detected.","specialisations":[]}


# ════════════════════════════════════════════════════════════════════
#  DEEP QUESTION GENERATION
# ════════════════════════════════════════════════════════════════════
def generate_questions(role: str, difficulty: str, q_type: str, count: int,
                       resume_info: dict, warmup: bool,
                       resume_text: str = "") -> list:
    """
    Generate deep, expert-level questions specific to the role.
    Each role has a custom strategy that ensures complex, non-basic questions.
    """
    strategy = DEEP_STRATEGIES.get(role, DEEP_STRATEGIES["Software Engineering"])

    diff_guide = {
        "Junior":    "intermediate-to-hard level — candidate has 1-2 years experience but should know concepts deeply",
        "Mid-Level": "hard level — candidate should demonstrate strong conceptual depth and production experience",
        "Senior":    "expert/principal level — architect-level thinking, system design, leadership trade-offs"
    }.get(difficulty, "hard")

    # Build resume context
    skills      = resume_info.get("skills", []) + resume_info.get("technologies", [])
    companies   = resume_info.get("companies", [])
    projects    = resume_info.get("projects", [])
    achievements= resume_info.get("key_achievements", [])
    exp_years   = resume_info.get("experience_years", 0)
    specialise  = resume_info.get("specialisations", [])

    resume_ctx = ""
    if skills:
        resume_ctx += f"\nCandidate's skills: {', '.join(skills[:10])}"
    if companies:
        resume_ctx += f"\nWorked at: {', '.join(companies[:3])}"
    if projects:
        resume_ctx += f"\nKey projects: {'; '.join(projects[:3])}"
    if achievements:
        resume_ctx += f"\nAchievements: {'; '.join(achievements[:3])}"
    if specialise:
        resume_ctx += f"\nSpecialisations: {', '.join(specialise[:4])}"
    if exp_years:
        resume_ctx += f"\nExperience: {exp_years} years"
    if resume_text and len(resume_text) > 100:
        resume_ctx += f"\n\nFULL RESUME EXCERPT:\n{resume_text[:1500]}"

    # Question type instruction
    type_inst = {
        "Technical": f"Generate ONLY technical/conceptual questions about {role}. Deep technical depth.",
        "Behavioural": f"Generate ONLY behavioural questions using STAR method context. Focus on: {strategy['behavioral_areas']}",
        "Mixed": f"Generate a mix: ~60% deep technical questions about {role}, ~40% behavioural questions from these areas: {strategy['behavioral_areas']}"
    }.get(q_type, "Mixed technical and behavioural")

    warmup_inst = ""
    warmup_q = []
    if warmup:
        warmup_q = [f"[WARMUP] Tell me briefly about your background and what specifically drew you to {role}. (warm-up — not scored)"]
        count_actual = count
    else:
        count_actual = count

    prompt = f"""You are an expert interviewer — Staff/Principal Engineer or Senior HR Leader — conducting a {difficulty} level {role} interview.

{strategy['depth_instruction']}

RESUME CONTEXT:{resume_ctx}

DIFFICULTY: {diff_guide}
QUESTION TYPE: {type_inst}

CRITICAL RULES:
1. Questions MUST be DEEP and COMPLEX — never ask "what is X?" or basic definitions
2. Ask questions that test HOW and WHY, not just WHAT
3. Reference the candidate's specific background, tools, companies, and projects from their resume
4. Every question should require at least 3-5 minutes of detailed expert answer
5. Include questions about trade-offs, failure scenarios, architectural decisions
6. For technical: ask about internals, edge cases, production challenges
7. For behavioural: ask about complex, ambiguous, high-stakes situations
8. Do NOT repeat similar questions — each must test a genuinely different dimension
9. Return ONLY a JSON array of exactly {count_actual} question strings

EXAMPLE DEPTH LEVEL (do not use these exact questions):
- Bad (too basic): "What is a REST API?"
- Good (deep): "You're designing a payment API that needs to handle exactly-once semantics across distributed services. Walk me through your idempotency key design, how you'd handle the race condition between payment creation and webhook delivery, and what changes if you need to support cross-currency transactions with regulatory audit requirements."

Generate {count_actual} deep questions now:
JSON array:"""

    raw = _ask(prompt, 0.65, 2200)

    try:
        qs = _parse_json(raw)
        qs = [str(q).strip() for q in qs if q and len(str(q)) > 30][:count_actual]
    except Exception:
        # fallback extraction
        lines = [l.strip() for l in raw.split("\n")
                 if len(l.strip()) > 40 and "?" in l]
        for i, l in enumerate(lines):
            for p in [f"{i+1}.", f"{i+1})", "-", "•", "*"]:
                if l.startswith(p): lines[i] = l[len(p):].strip()
        qs = lines[:count_actual]

    # Fallbacks if generation fails
    if len(qs) < count_actual:
        fallbacks = _fallback_questions(role, q_type)
        while len(qs) < count_actual and fallbacks:
            qs.append(fallbacks.pop(0))

    return warmup_q + qs


def _fallback_questions(role: str, q_type: str) -> list:
    """Deep fallback questions per role if AI generation fails."""
    fb = {
        "Software Engineering": [
            "You need to design a rate limiter for an API serving 10M requests/day across 50 geographic regions. Walk me through the algorithm choice, where you'd store state, how you'd handle Redis failover, and what trade-offs you'd accept between accuracy and performance.",
            "Explain how you'd architect a real-time collaborative document editor (like Google Docs). How do you handle conflict resolution, operational transforms vs CRDTs, and what happens to pending operations during a network partition?",
            "Your monolithic application needs to be broken into microservices without downtime. Describe your strangler fig pattern implementation, how you'd handle the distributed data problem, and what you'd do differently if you could start over.",
            "A memory leak is slowly degrading a production JVM service over 72 hours. Walk me through your debugging methodology, the tools you'd use, and how you'd deploy a fix without a restart.",
            "Design a system that guarantees exactly-once message processing in a distributed pipeline where the consumer can fail at any point. Explain every trade-off in your design.",
        ],
        "Data Science": [
            "Your churn prediction model has 90% accuracy but your product team says it's useless. Explain why accuracy is a misleading metric here, what metrics actually matter, and how you'd redesign the evaluation framework to align with business value.",
            "You discover your production ML model's performance has degraded significantly over 6 months. Walk me through your complete drift detection strategy, how you'd distinguish data drift from concept drift, and your model refresh policy design.",
            "Explain the mathematical relationship between L1 and L2 regularisation. When would L1 produce a better production model than L2, and why? Include a real scenario where you'd choose elastic net instead.",
            "You need to run an A/B test for a recommendation algorithm change, but the network effects mean user behaviour is interdependent. How does this violate SUTVA, what are your options, and how do you calculate the minimum detectable effect given 30% day-over-day user overlap?",
            "Describe how you'd build a real-time fraud detection system that must make decisions in under 50ms. What features are feasible, what model architecture works at this latency, and how do you handle the cold start problem for new cards?",
        ],
        "Frontend Engineering": [
            "Explain exactly what happens in the browser between a user typing a URL and the first pixel being painted. Where are the opportunities to optimise each phase, and how do Core Web Vitals map onto this pipeline?",
            "You inherit a React application where every user interaction causes full re-renders across 200+ components. Describe your systematic debugging approach, the tools you'd use, and your optimisation strategy without rewriting the entire application.",
            "Design a component library that needs to work across React, Vue, and Angular codebases in your organisation. Compare Web Components, design tokens + framework-specific wrappers, and a monorepo with separate packages — include build pipeline implications.",
            "Your SPA has a JavaScript bundle of 4MB causing a 12-second TTI on 3G. Walk me through your complete performance audit and remediation plan, including how you'd measure the impact of each change.",
            "Explain how you'd implement optimistic UI updates for a collaborative feature where two users might edit the same data simultaneously. Cover the conflict resolution strategy, rollback mechanism, and what you'd tell the user when conflicts occur.",
        ],
        "Backend Engineering": [
            "Design a distributed job scheduling system that needs to guarantee no job runs more than once, handles worker failures gracefully, and supports job dependencies with fan-out/fan-in patterns. Walk through every failure scenario.",
            "Your PostgreSQL query that takes 200ms in staging takes 45 seconds in production with the same data volume. Describe your complete investigation process, the query planner information you'd examine, and five different optimisation strategies you'd try in order.",
            "Explain the complete OAuth 2.0 authorisation code flow with PKCE. Why is each step necessary? What specific attacks does PKCE prevent, and how would you implement token rotation with refresh token reuse detection?",
            "You need to migrate a 2TB PostgreSQL database to a new schema with zero downtime and the ability to roll back. Walk through your complete strategy including the application changes required.",
            "Design a webhook delivery system that guarantees at-least-once delivery to unreliable third-party endpoints, handles back-pressure when endpoints are slow, and provides customers with delivery logs and retry controls.",
        ],
        "HR Management": [
            "You've been asked to design a performance management system for a 2,000-person engineering organisation where the CEO wants forced ranking but your data shows it increases voluntary attrition of high performers by 23%. How do you navigate this, what alternative do you propose, and how do you present the business case?",
            "Walk me through designing a compensation structure for a company expanding from single-country to 12 countries simultaneously, including how you'd handle pay equity, local market benchmarking, equity refresh grants for existing employees, and the communication strategy.",
            "You discover through HR analytics that women in your engineering organisation are promoted 18 months later than men with equivalent performance ratings. How do you investigate the root cause, what systemic interventions would you design, and how do you measure whether they worked?",
            "A high-performing SVP has a pattern of behaviour that doesn't rise to legal termination threshold but is creating psychological safety issues for their team of 200 people. You have data showing their team's engagement scores declining 15% year-over-year. What's your strategy?",
            "Design a talent acquisition strategy to hire 300 engineers in 18 months in a market where your employer brand is unknown and you're competing with FAANG. Include sourcing channel mix, interview process design to reduce time-to-offer below 2 weeks, and how you'd measure quality of hire.",
        ],
    }
    return fb.get(role, fb["Software Engineering"])[:]


# ════════════════════════════════════════════════════════════════════
#  ANSWER EVALUATION — 5 metrics
# ════════════════════════════════════════════════════════════════════
def evaluate_answer(question: str, answer: str, role: str,
                    difficulty: str, q_type: str) -> dict:
    depth_standard = {
        "Junior": "intermediate practitioner who understands concepts beyond textbook definitions",
        "Mid-Level": "experienced engineer/professional with production depth and clear reasoning",
        "Senior": "principal/staff level — architectural thinking, nuanced trade-offs, leadership context"
    }.get(difficulty, "experienced professional")

    prompt = f"""You are evaluating a {difficulty} {role} candidate's answer to a DEEP interview question.

QUESTION: {question}

CANDIDATE'S ANSWER: {answer}

EVALUATION STANDARD: Answer should demonstrate {depth_standard} level knowledge.

Return ONLY a valid JSON object:
{{
    "score": <integer 1-10>,
    "technical_score": <integer 1-10, accuracy and depth of technical/domain content>,
    "communication_score": <integer 1-10, clarity, structure, logical flow>,
    "confidence_score": <integer 1-10, assertiveness, specificity, avoiding vague hedging>,
    "tone_score": <integer 1-10, professionalism, positivity, ownership language>,
    "summary": "<one punchy verdict sentence — be direct and specific>",
    "strengths": "<2-3 specific sentences on what demonstrated real expertise>",
    "weaknesses": "<2-3 specific sentences on what was missing or shallow>",
    "improvement": "<2-3 very specific, actionable sentences — what to add, study, or demonstrate>",
    "model_answer_hint": "<2 sentences on what a 9-10/10 answer would additionally include>",
    "star_used": <true if behavioural answer used Situation-Task-Action-Result structure>,
    "key_concepts_missing": ["concept1","concept2","concept3"],
    "follow_up_question": "<one natural follow-up question based on what they said>",
    "sentiment": "<positive|neutral|negative>"
}}

SCORING:
1-3: Off-topic, fundamentally wrong, or dangerously shallow
4-5: Surface level — textbook knowledge, no production depth
6-7: Good practitioner knowledge — correct, some depth, missing nuance
8-9: Strong — specific, demonstrates real experience, good trade-off awareness
10: Exceptional — every dimension covered, nuanced, could teach this topic

JSON:"""
    raw = _ask(prompt, 0.2, 900)
    try:
        r = _parse_json(raw)
        for f in ['score','technical_score','communication_score','confidence_score','tone_score']:
            r[f] = max(1, min(10, int(r.get(f, 5))))
        r.setdefault('summary',          'Answer evaluated.')
        r.setdefault('strengths',        'Some relevant knowledge demonstrated.')
        r.setdefault('weaknesses',       'Needs more technical depth and specificity.')
        r.setdefault('improvement',      'Study the internals and be more specific with production examples.')
        r.setdefault('model_answer_hint','A top answer includes trade-offs, edge cases, and real-world context.')
        r.setdefault('star_used',        False)
        r.setdefault('key_concepts_missing', [])
        r.setdefault('follow_up_question', '')
        r.setdefault('sentiment',        'neutral')
        return r
    except Exception:
        return {"score":5,"technical_score":5,"communication_score":5,
                "confidence_score":5,"tone_score":5,
                "summary":"Answer evaluated — see details.",
                "strengths":"Attempted to address the question.",
                "weaknesses":"Needs deeper technical specificity.",
                "improvement":"Study internals and use concrete production examples.",
                "model_answer_hint":"Include trade-offs, edge cases, and specific metrics.",
                "star_used":False,"key_concepts_missing":[],"follow_up_question":"","sentiment":"neutral"}


# ════════════════════════════════════════════════════════════════════
#  ACHIEVEMENTS
# ════════════════════════════════════════════════════════════════════
def compute_achievements(session_id, evaluations, pct, difficulty, is_first):
    badges = []
    scores = [e.get('score', 0) for e in evaluations if e.get('score', 0) > 0]
    avg    = sum(scores) / len(scores) if scores else 0

    if is_first:
        badges.append(("First Interview",       "🎯"))
    if avg >= 8:
        badges.append(("High Scorer",           "⭐"))
    if avg >= 9:
        badges.append(("Expert Level",          "🏆"))
    if difficulty == "Senior":
        badges.append(("Senior Challenger",     "🔥"))
    if len(scores) == len(evaluations) and len(evaluations) > 0:
        badges.append(("Full Completion",       "💯"))
    if any(e.get('star_used') for e in evaluations):
        badges.append(("STAR Method Expert",    "🌟"))
    if avg >= 7 and difficulty in ("Mid-Level", "Senior"):
        badges.append(("Deep Thinker",          "🧠"))
    return [(name, emoji) for name, emoji in badges]