import re
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable
from langchain_ollama import OllamaLLM


# ── Deterministic Tools ───────────────────────────────────────────────────────

WEAK_PHRASES = {
    "responsible for", "worked on", "helped with", "assisted",
    "involved in", "participated in", "contributed to", "tasked with",
    "was part of", "helped to",
}

TECH_KEYWORDS = {
    "python", "javascript", "typescript", "java", "c++", "c#", "go", "rust",
    "react", "angular", "vue", "node.js", "django", "fastapi", "flask", "spring",
    "sql", "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "ci/cd",
    "machine learning", "deep learning", "nlp", "computer vision",
    "git", "agile", "scrum", "rest", "graphql", "microservices", "linux",
}


def tool_find_weak_phrases(text: str) -> list[str]:
    lower = text.lower()
    return [p for p in WEAK_PHRASES if p in lower]


def tool_find_quantified_bullets(text: str) -> tuple[list[str], list[str]]:
    bullets = re.findall(r'(?:^|\n)\s*[•\-\*]\s*(.+)', text)
    quantified = [b for b in bullets if re.search(r'\d', b)]
    unquantified = [b for b in bullets if not re.search(r'\d', b)]
    return quantified, unquantified


def tool_extract_tech_keywords(text: str) -> list[str]:
    lower = text.lower()
    return sorted(kw for kw in TECH_KEYWORDS if kw in lower)


def tool_parse_diff(diff: str) -> tuple[list[str], list[str]]:
    added = [
        l[1:].strip() for l in diff.splitlines()
        if l.startswith('+') and not l.startswith('+++') and l[1:].strip()
    ]
    removed = [
        l[1:].strip() for l in diff.splitlines()
        if l.startswith('-') and not l.startswith('---') and l[1:].strip()
    ]
    return added, removed


# ── Agent Result ──────────────────────────────────────────────────────────────

@dataclass
class AgentResult:
    name: str
    report: str
    tool_data: dict = field(default_factory=dict)
    error: str | None = None


# ── Specialist Agents ─────────────────────────────────────────────────────────

class ContentQualityAgent:
    name = "Content Quality"

    def run(self, llm: OllamaLLM, cv_text: str, diff: str) -> AgentResult:
        weak = tool_find_weak_phrases(cv_text)
        quantified, unquantified = tool_find_quantified_bullets(cv_text)
        total = len(quantified) + len(unquantified)
        ratio = f"{len(quantified)}/{total}" if total else "0/0"

        tool_data = {
            "weak_phrases_found": weak,
            "quantified_bullets": len(quantified),
            "unquantified_bullets": len(unquantified),
        }

        prompt = f"""You are a CV writing expert. Tool scans on this CV returned:
- Weak phrases detected: {weak if weak else "none"}
- Achievement quantification: {ratio} bullets contain numbers
- Unquantified bullet samples: {unquantified[:3]}

CV TEXT:
{cv_text[:2500]}

Provide content quality feedback in 3-5 sentences:
1. For each weak phrase found, suggest a stronger replacement verb
2. Comment on the {ratio} quantification ratio and name specific bullets to improve
3. Identify the 2 highest-impact writing changes"""

        try:
            return AgentResult(name=self.name, report=llm.invoke(prompt).strip(), tool_data=tool_data)
        except Exception as e:
            return AgentResult(name=self.name, report="", tool_data=tool_data, error=str(e))


class ATSAgent:
    name = "ATS Optimization"

    def run(self, llm: OllamaLLM, cv_text: str, diff: str) -> AgentResult:
        keywords = tool_extract_tech_keywords(cv_text)
        tool_data = {"detected_keywords": keywords, "keyword_count": len(keywords)}

        prompt = f"""You are an ATS (Applicant Tracking System) specialist. Keyword scan results:
- Detected tech keywords ({len(keywords)}): {keywords}

CV TEXT:
{cv_text[:2000]}

ATS feedback in 3-5 sentences:
1. Are these keywords appropriate for the apparent target role?
2. Name 3-5 high-value keywords that are missing
3. Any formatting red flags that hurt ATS parsing (tables, columns, graphics, non-standard headers)?"""

        try:
            return AgentResult(name=self.name, report=llm.invoke(prompt).strip(), tool_data=tool_data)
        except Exception as e:
            return AgentResult(name=self.name, report="", tool_data=tool_data, error=str(e))


class DiffAnalyzerAgent:
    name = "Change Analysis"

    def run(self, llm: OllamaLLM, cv_text: str, diff: str) -> AgentResult:
        added, removed = tool_parse_diff(diff)
        tool_data = {"lines_added": len(added), "lines_removed": len(removed)}

        prompt = f"""You are a CV change analyst. Diff parser results:
- Lines added ({len(added)}): {added[:8]}
- Lines removed ({len(removed)}): {removed[:8]}

Analyze the changes in 2-4 sentences:
1. What is the user's apparent intent behind these edits?
2. Did the changes make the CV stronger or weaker overall?
3. Any new inconsistencies or regressions introduced?"""

        try:
            return AgentResult(name=self.name, report=llm.invoke(prompt).strip(), tool_data=tool_data)
        except Exception as e:
            return AgentResult(name=self.name, report="", tool_data=tool_data, error=str(e))


class StrategicAdvisorAgent:
    name = "Strategic Advice"

    def run(
        self,
        llm: OllamaLLM,
        cv_text: str,
        previous_feedback: str | None,
    ) -> AgentResult:
        prev_ctx = f"\nPREVIOUS FEEDBACK GIVEN:\n{previous_feedback[:600]}" if previous_feedback else ""

        prompt = f"""You are a senior career strategist.{prev_ctx}

CV:
{cv_text[:3000]}

Strategic assessment in 2-3 sentences:
1. The single highest-impact change that would most improve job prospects
2. Is the CV targeting the right seniority level and role for this person's experience?
3. Did the user act on previous feedback? (skip if no previous feedback)"""

        try:
            return AgentResult(name=self.name, report=llm.invoke(prompt).strip())
        except Exception as e:
            return AgentResult(name=self.name, report="", error=str(e))


# ── Orchestrator ──────────────────────────────────────────────────────────────

def run_multi_agent_analysis(
    llm: OllamaLLM,
    cv_text: str,
    diff: str,
    previous_feedback: str | None = None,
    on_agent_complete: Callable[[str, str, dict], None] | None = None,
) -> str:
    parallel_agents: list[ContentQualityAgent | ATSAgent | DiffAnalyzerAgent] = [
        ContentQualityAgent(),
        ATSAgent(),
        DiffAnalyzerAgent(),
    ]

    results: list[AgentResult] = []

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(a.run, llm, cv_text, diff): a for a in parallel_agents}
        for future in as_completed(futures):
            r = future.result()
            results.append(r)
            if on_agent_complete and not r.error:
                on_agent_complete(r.name, r.report, r.tool_data)

    strategic = StrategicAdvisorAgent().run(llm, cv_text, previous_feedback)
    results.append(strategic)
    if on_agent_complete and not strategic.error:
        on_agent_complete(strategic.name, strategic.report, strategic.tool_data)

    agent_reports = "\n\n".join(
        f"### {r.name} Agent\n{r.report}"
        for r in results
        if r.report and not r.error
    )

    synthesis_prompt = f"""You are a synthesis agent. Four CV specialist agents produced these reports:

{agent_reports}

Combine their findings into one final prioritized CV review using markdown:

## Summary of Changes
(1-2 sentences on what changed and the overall direction)

## Top 3 Priority Fixes
1. (most impactful)
2.
3.

## What's Working Well
- (1-2 genuine strengths)

## Next Step
(single most important action the user should take right now)"""

    return llm.invoke(synthesis_prompt).strip()
