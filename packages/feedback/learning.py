from statistics import median
from sqlalchemy import select
from packages.core.models import Draft, Pattern


def recommendations(session, rankings):
    """Evidence summaries only; never change publishing approval or fabricate a causal reward."""
    drafts = session.scalars(select(Draft).where(Draft.state == "published")).all()
    output = []
    for pattern in session.scalars(select(Pattern)).all():
        experiments = [d for d in drafts if d.pattern_id == pattern.id and d.published_post_id]
        evidence = [{"draft_id": d.id, "post_id": d.published_post_id, "url": d.remote_url, "rank": rankings.get(d.published_post_id)} for d in experiments]
        values = [e["rank"]["engagement_percentile"] for e in evidence if e["rank"] and e["rank"]["status"] == "ok" and e["rank"]["engagement_percentile"] is not None]
        enough = len(values) >= 5
        output.append({"pattern_id": pattern.id, "name": pattern.name, "supporting_posts": len(pattern.example_post_ids), "generated_variants": len(session.scalars(select(Draft).where(Draft.pattern_id == pattern.id)).all()), "measured_experiments": len(experiments), "comparable_experiments": len(values), "median_engagement_percentile": median(values) if enough else None, "recommendation": ("test_more_variants" if median(values) >= 75 else "revise_and_retest") if enough else "collect_more_evidence", "status": "observational" if enough else "insufficient_baseline", "evidence": evidence, "caveat": "Selection bias and confounding remain; this is not causal proof or a success guarantee."})
    return output
