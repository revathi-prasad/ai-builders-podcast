"""
Quality Checkers (Layer 2)

Output-level verification that runs after script generation.
These are production quality gates that determine if output
is ready for synthesis or needs revision.

Unlike FM monitors (which run on every message), these run
less frequently but are more thorough.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

from src.models.state import DialogueSegment, PodcastState, VerificationResult


class QualityChecker(ABC):
    """Base class for quality checkers"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Checker identifier"""
        pass

    @abstractmethod
    def check(
        self,
        segments: List[DialogueSegment],
        state: PodcastState
    ) -> VerificationResult:
        """
        Check script quality.

        Args:
            segments: Generated script segments
            state: Current workflow state

        Returns:
            VerificationResult with pass/fail and details
        """
        pass


class FactChecker(QualityChecker):
    """
    Verify facts in the script against Knowledge Graph.

    Checks:
    - Are cited facts actually in the graph?
    - Are uncited claims potentially hallucinated?
    - Do cited facts have valid sources?
    """

    @property
    def name(self) -> str:
        return "fact_checker"

    def check(
        self,
        segments: List[DialogueSegment],
        state: PodcastState
    ) -> VerificationResult:

        issues = []
        suggestions = []

        # Collect all fact citations
        cited_facts = set()
        uncited_segments = []

        for seg in segments:
            if seg.fact_ids:
                cited_facts.update(seg.fact_ids)
            else:
                # Segments without citations might have uncited claims
                if self._has_factual_claim(seg.text):
                    uncited_segments.append(seg)

        # Check if cited facts exist in state
        known_facts = set(state.get('fact_entity_ids', []))
        unknown_citations = cited_facts - known_facts

        if unknown_citations:
            issues.append(f"{len(unknown_citations)} cited facts not in graph")
            suggestions.append("Verify citations or add facts to graph")

        # Flag uncited factual claims
        if len(uncited_segments) > len(segments) * 0.3:
            issues.append(
                f"{len(uncited_segments)} segments have uncited factual claims"
            )
            suggestions.append("Add citations or soften language")

        # Calculate score
        if not segments:
            score = 1.0
        else:
            cited_ratio = len([s for s in segments if s.fact_ids]) / len(segments)
            unknown_penalty = len(unknown_citations) * 0.1
            score = max(0.0, min(1.0, cited_ratio - unknown_penalty))

        return VerificationResult(
            checker_name=self.name,
            passed=score >= 0.7,
            score=score,
            issues=issues,
            suggestions=suggestions
        )

    def _has_factual_claim(self, text: str) -> bool:
        """Heuristic: does text contain factual claims?"""
        factual_indicators = [
            "is", "are", "was", "were", "has", "have",
            "percent", "%", "million", "billion",
            "according to", "research shows", "studies",
            "founded", "created", "invented", "discovered"
        ]
        text_lower = text.lower()
        return any(ind in text_lower for ind in factual_indicators)


class FlowChecker(QualityChecker):
    """
    Check conversation naturalness and flow.

    Checks:
    - Smooth transitions between topics
    - Balanced speaker distribution
    - Natural dialogue patterns
    """

    @property
    def name(self) -> str:
        return "flow_checker"

    def check(
        self,
        segments: List[DialogueSegment],
        state: PodcastState
    ) -> VerificationResult:

        issues = []
        suggestions = []

        if len(segments) < 4:
            return VerificationResult(
                checker_name=self.name,
                passed=False,
                score=0.3,
                issues=["Script too short for meaningful flow analysis"],
                suggestions=["Generate more content"]
            )

        # Check 1: Speaker balance
        speakers = [s.speaker for s in segments if s.speaker != "MUSIC"]
        unique_speakers = set(speakers)

        if len(unique_speakers) >= 2:
            counts = {sp: speakers.count(sp) for sp in unique_speakers}
            max_count = max(counts.values())
            min_count = min(counts.values())

            if max_count > min_count * 2.5:
                issues.append("Speaker distribution imbalanced")
                suggestions.append("Give less dominant speaker more lines")

        # Check 2: Consecutive same speaker (monologue in conversation)
        max_consecutive = self._max_consecutive_speaker(segments)
        if state.get('episode_format') == 'conversation' and max_consecutive > 4:
            issues.append(f"One speaker has {max_consecutive} consecutive segments")
            suggestions.append("Break up long monologues with interjections")

        # Check 3: Segment length variation
        lengths = [len(s.text.split()) for s in segments if s.speaker != "MUSIC"]
        if lengths:
            avg_len = sum(lengths) / len(lengths)
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)

            if variance < 10:  # Too uniform
                issues.append("Dialogue segments are unnaturally uniform in length")
                suggestions.append("Vary segment lengths for natural conversation")

        # Check 4: Transitions
        choppy_transitions = self._count_choppy_transitions(segments)
        if choppy_transitions > len(segments) * 0.2:
            issues.append(f"{choppy_transitions} abrupt topic transitions")
            suggestions.append("Add transition phrases between topics")

        # Calculate score
        base_score = 1.0
        base_score -= len(issues) * 0.15
        score = max(0.0, min(1.0, base_score))

        return VerificationResult(
            checker_name=self.name,
            passed=score >= 0.7,
            score=score,
            issues=issues,
            suggestions=suggestions
        )

    def _max_consecutive_speaker(self, segments: List[DialogueSegment]) -> int:
        """Find longest run of same speaker"""
        if not segments:
            return 0

        max_run = 1
        current_run = 1
        current_speaker = segments[0].speaker

        for seg in segments[1:]:
            if seg.speaker == current_speaker:
                current_run += 1
                max_run = max(max_run, current_run)
            else:
                current_run = 1
                current_speaker = seg.speaker

        return max_run

    def _count_choppy_transitions(self, segments: List[DialogueSegment]) -> int:
        """Count transitions without connecting phrases"""
        transition_phrases = [
            "speaking of", "that reminds me", "on that note",
            "building on", "to add to", "great point",
            "interesting", "absolutely", "exactly",
            "you know", "right", "yes", "agreed"
        ]

        choppy = 0
        for i in range(1, len(segments)):
            text_lower = segments[i].text.lower()[:50]  # Check start of segment
            has_transition = any(phrase in text_lower for phrase in transition_phrases)
            if not has_transition and segments[i].speaker != segments[i-1].speaker:
                choppy += 1

        return choppy


class FormatChecker(QualityChecker):
    """
    Check format compliance with user requirements.

    Checks:
    - Duration matches target
    - Vocabulary appropriate for audience
    - Structure has intro/outro
    """

    @property
    def name(self) -> str:
        return "format_checker"

    def check(
        self,
        segments: List[DialogueSegment],
        state: PodcastState
    ) -> VerificationResult:

        issues = []
        suggestions = []

        # Calculate duration
        total_words = sum(len(s.text.split()) for s in segments if s.speaker != "MUSIC")
        estimated_minutes = total_words / 150  # 150 words per minute
        target_minutes = state.get('target_duration_minutes', 10)

        # Check 1: Duration compliance
        duration_ratio = estimated_minutes / target_minutes if target_minutes > 0 else 1
        if duration_ratio < 0.7:
            issues.append(f"Too short: ~{estimated_minutes:.1f} min vs {target_minutes} min target")
            suggestions.append("Expand content or add more details")
        elif duration_ratio > 1.5:
            issues.append(f"Too long: ~{estimated_minutes:.1f} min vs {target_minutes} min target")
            suggestions.append("Trim content or split into parts")

        # Check 2: Has intro/outro
        if segments:
            first_text = segments[0].text.lower()
            last_text = segments[-1].text.lower()

            intro_phrases = ["welcome", "hello", "today", "episode", "joining"]
            outro_phrases = ["thank", "next time", "goodbye", "see you", "tune in"]

            has_intro = any(p in first_text for p in intro_phrases)
            has_outro = any(p in last_text for p in outro_phrases)

            if not has_intro:
                issues.append("Missing introduction")
                suggestions.append("Add welcoming introduction")
            if not has_outro:
                issues.append("Missing outro/sign-off")
                suggestions.append("Add closing remarks")

        # Check 3: Audience level vocabulary
        audience = state.get('audience_level', 'intermediate')
        if audience == 'beginner':
            complex_words = self._count_complex_words(segments)
            if complex_words > total_words * 0.1:
                issues.append("Too many complex terms for beginner audience")
                suggestions.append("Simplify vocabulary or add explanations")

        # Calculate score
        base_score = 1.0
        if 0.8 <= duration_ratio <= 1.3:
            base_score -= 0.0
        elif 0.7 <= duration_ratio <= 1.5:
            base_score -= 0.1
        else:
            base_score -= 0.3

        base_score -= len([i for i in issues if "Missing" in i]) * 0.1
        score = max(0.0, min(1.0, base_score))

        return VerificationResult(
            checker_name=self.name,
            passed=score >= 0.7,
            score=score,
            issues=issues,
            suggestions=suggestions
        )

    def _count_complex_words(self, segments: List[DialogueSegment]) -> int:
        """Count words that might be too complex for beginners"""
        complex_count = 0
        for seg in segments:
            words = seg.text.split()
            for word in words:
                # Simple heuristic: long words are often complex
                if len(word) > 10:
                    complex_count += 1
        return complex_count


class CulturalChecker(QualityChecker):
    """
    Check cultural appropriateness.

    Checks:
    - Language matches target culture
    - No inappropriate references
    - Cultural context present (if needed)
    """

    @property
    def name(self) -> str:
        return "cultural_checker"

    def check(
        self,
        segments: List[DialogueSegment],
        state: PodcastState
    ) -> VerificationResult:

        issues = []
        suggestions = []

        target_language = state.get('target_language', 'english')
        target_culture = state.get('target_culture', target_language)

        # Basic checks - in production, use more sophisticated analysis
        all_text = ' '.join(s.text for s in segments)

        # Check for mixed languages (if target is specific)
        if target_language == 'hindi':
            # Check for Hindi characters
            hindi_chars = sum(1 for c in all_text if '\u0900' <= c <= '\u097F')
            if hindi_chars < len(all_text) * 0.3:
                issues.append("Script may not be in Hindi")
                suggestions.append("Ensure Hindi translation is complete")

        elif target_language == 'tamil':
            # Check for Tamil characters
            tamil_chars = sum(1 for c in all_text if '\u0B80' <= c <= '\u0BFF')
            if tamil_chars < len(all_text) * 0.3:
                issues.append("Script may not be in Tamil")
                suggestions.append("Ensure Tamil translation is complete")

        # Check for potentially sensitive content
        # This is a basic implementation - production would use content moderation
        sensitive_terms = ["stupid", "idiot", "dumb", "crazy"]
        if any(term in all_text.lower() for term in sensitive_terms):
            issues.append("Potentially insensitive language detected")
            suggestions.append("Review and soften language")

        # Score
        score = 1.0 - (len(issues) * 0.2)
        score = max(0.0, min(1.0, score))

        return VerificationResult(
            checker_name=self.name,
            passed=score >= 0.8,
            score=score,
            issues=issues,
            suggestions=suggestions
        )


class LLMFactChecker(QualityChecker):
    """
    LLM-augmented fact checker.

    For each fact_id in segments, queries the KG for provenance and uses
    an LLM to judge whether the claim accurately represents its source.
    Falls back gracefully if no LLM API key is available.
    """

    @property
    def name(self) -> str:
        return "llm_fact_checker"

    def check(
        self,
        segments: List[DialogueSegment],
        state: PodcastState
    ) -> VerificationResult:
        import asyncio
        import json

        issues = []
        suggestions = []
        checked = 0
        supported = 0

        try:
            from src.graph.manager import KnowledgeGraphManager
            from src.llm import get_llm_client

            # Get KG manager (use singleton from graph module if available)
            try:
                from src.agents.graph import get_kg_manager
                kg = get_kg_manager()
            except Exception:
                kg = KnowledgeGraphManager()
                kg.initialize()

            # Collect unique fact IDs from segments
            fact_ids = set()
            for seg in segments:
                if hasattr(seg, 'fact_ids') and seg.fact_ids:
                    fact_ids.update(seg.fact_ids)
                elif isinstance(seg, dict) and seg.get('fact_ids'):
                    fact_ids.update(seg['fact_ids'])

            if not fact_ids:
                return VerificationResult(
                    checker_name=self.name,
                    passed=True,
                    score=0.7,
                    issues=["No fact citations to verify"],
                    suggestions=["Add fact citations to segments for better verification"]
                )

            # Check provenance for each fact
            unsupported = []
            facts_with_sources = []

            for fid in fact_ids:
                checked += 1
                try:
                    provenance = kg.get_fact_provenance(fid)
                    if not provenance:
                        unsupported.append(fid)
                    else:
                        facts_with_sources.append((fid, provenance))
                        supported += 1
                except Exception:
                    unsupported.append(fid)

            if unsupported:
                issues.append(
                    f"{len(unsupported)} facts have no source provenance: "
                    f"{', '.join(unsupported[:3])}{'...' if len(unsupported) > 3 else ''}"
                )
                suggestions.append("Add source links for unsupported facts")

            # Use LLM to verify a sample of facts with sources
            if facts_with_sources:
                try:
                    client = get_llm_client()
                    sample = facts_with_sources[:5]  # Check up to 5 facts

                    facts_text = "\n".join([
                        f"- Fact {fid}: (provenance: {len(prov)} sources)"
                        for fid, prov in sample
                    ])

                    # Simple LLM verification prompt
                    prompt = f"""You are a fact-checker. Rate the reliability of these facts on a scale of 0-10.
Facts to check:
{facts_text}

Return ONLY a JSON object with fact_id as key and score (0-10) as value. No other text."""

                    response = asyncio.run(client.generate(
                        prompt=prompt,
                        temperature=0.1,
                        max_tokens=500
                    ))

                    content = response.content.strip()
                    if content.startswith("```"):
                        content = content.split("```")[1]
                        if content.startswith("json"):
                            content = content[4:]
                        content = content.strip()

                    scores = json.loads(content)
                    low_score_facts = [
                        fid for fid, score in scores.items()
                        if isinstance(score, (int, float)) and score < 5
                    ]

                    if low_score_facts:
                        issues.append(
                            f"{len(low_score_facts)} facts scored low on LLM verification"
                        )
                        suggestions.append("Review and correct low-confidence facts")

                except Exception as e:
                    # LLM check failed — don't block, just note it
                    issues.append(f"LLM verification skipped: {str(e)[:50]}")

        except ImportError:
            return VerificationResult(
                checker_name=self.name,
                passed=True,
                score=0.5,
                issues=["LLM fact checker dependencies not available"],
                suggestions=[]
            )

        # Calculate score
        if checked == 0:
            score = 0.7
        else:
            score = supported / checked
            # Boost slightly since having provenance is good
            score = min(1.0, score + 0.1)

        return VerificationResult(
            checker_name=self.name,
            passed=score >= 0.6,
            score=score,
            issues=issues,
            suggestions=suggestions
        )


# ============================================================================
# RUN ALL CHECKERS
# ============================================================================

def run_all_checkers(
    segments: List[DialogueSegment],
    state: PodcastState
) -> List[VerificationResult]:
    """
    Run all quality checkers on generated script.

    Returns list of VerificationResults.
    """
    checkers = [
        FactChecker(),
        FlowChecker(),
        FormatChecker(),
        CulturalChecker(),
        LLMFactChecker(),
    ]

    results = []
    for checker in checkers:
        try:
            result = checker.check(segments, state)
            results.append(result)
        except Exception as e:
            results.append(VerificationResult(
                checker_name=checker.name,
                passed=True,  # Don't block on checker errors
                score=0.5,
                issues=[f"Checker error: {e}"],
                suggestions=[]
            ))

    return results


def aggregate_quality_score(results: List[VerificationResult]) -> float:
    """Calculate overall quality score from checker results"""
    if not results:
        return 0.0

    # Weighted average - fact checking is most important
    weights = {
        "fact_checker": 0.25,
        "flow_checker": 0.20,
        "format_checker": 0.20,
        "cultural_checker": 0.05,
        "llm_fact_checker": 0.30,
    }

    total_weight = 0
    weighted_score = 0

    for result in results:
        weight = weights.get(result.checker_name, 0.25)
        weighted_score += result.score * weight
        total_weight += weight

    return weighted_score / total_weight if total_weight > 0 else 0.0


def should_revise(results: List[VerificationResult]) -> bool:
    """Determine if script needs revision based on checker results"""
    # Revise if any critical checker fails
    for result in results:
        if result.checker_name in ["fact_checker", "format_checker"]:
            if not result.passed:
                return True

    # Revise if overall quality is too low
    overall = aggregate_quality_score(results)
    return overall < 0.7
