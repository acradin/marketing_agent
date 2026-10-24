from datetime import datetime
from statistics import median


def age_bucket(post, snapshot):
    if not post.published_at:
        return None
    hours = (datetime.fromisoformat(snapshot.observed_at) - datetime.fromisoformat(post.published_at)).total_seconds() / 3600
    if hours < 0:
        return None
    return next((i for i, bound in enumerate((1, 6, 24, 72, 168, 720)) if hours <= bound), 6)


def signature(snapshot):
    return tuple(k for k in ("likes", "comments", "shares", "saves") if snapshot.metrics.get(k) is not None)


def engagement(snapshot):
    keys = signature(snapshot)
    return sum(snapshot.metrics[k] for k in keys) if keys else None


def follower_bucket(snapshot):
    n = snapshot.metrics.get("author_followers")
    return None if n is None else next((i for i, b in enumerate((1000, 10000, 100000, 1000000)) if n < b), 4)


def percentile(value, values):
    return 100 * (sum(x < value for x in values) + .5 * sum(x == value for x in values)) / len(values)


def rank(post, snapshots, cohort, minimum=5):
    result = {"status": "insufficient_baseline", "engagement_percentile": None, "relative_performance": None, "relative_performance_percentile": None, "growth_per_hour": None, "growth_percentile": None, "engagement_rate": None, "partial_engagement_rate": None, "confidence_score": 0, "sample_size": 0, "author_sample_size": 0, "warnings": [], "paid_promotion": post.paid_promotion}
    if not snapshots:
        return result
    snapshots = sorted(snapshots, key=lambda s: s.observed_at)
    latest = snapshots[-1]
    e, keys = engagement(latest), signature(latest)
    result["available_engagement_fields"] = keys
    result["missing_metrics"] = [k for k in ("views", "likes", "comments", "shares", "saves", "author_followers") if latest.metrics.get(k) is None]
    bucket = age_bucket(post, latest)
    if bucket is None:
        result["warnings"].append("unknown_or_invalid_post_age")
    if follower_bucket(latest) is None:
        result["warnings"].append("unknown_account_size")
    views = latest.metrics.get("views")
    if e is not None and views and views > 0:
        result["engagement_rate" if len(keys) == 4 else "partial_engagement_rate"] = e / views
    if len(snapshots) >= 2 and signature(snapshots[-2]) == keys and e is not None:
        previous = snapshots[-2]
        hours = (datetime.fromisoformat(latest.observed_at) - datetime.fromisoformat(previous.observed_at)).total_seconds() / 3600
        if hours > 0:
            delta = e - engagement(previous)
            if delta < 0:
                result["warnings"].append("counter_decreased_or_collection_error")
            else:
                result["growth_per_hour"] = delta / hours
    peers = [(p, s) for p, s in cohort if p.id != post.id and p.platform == post.platform and p.content_type == post.content_type and bucket is not None and age_bucket(p, s) == bucket and signature(s) == keys and s.source == latest.source and follower_bucket(s) == follower_bucket(latest) and p.paid_promotion == post.paid_promotion and engagement(s) is not None]
    values = [engagement(s) for _, s in peers]
    result["sample_size"] = len(values)
    author_values = [engagement(s) for p, s in peers if post.author_id is not None and p.author_id == post.author_id]
    result["author_sample_size"] = len(author_values)
    if e is not None and len(author_values) >= minimum:
        result["relative_performance"] = (e + 1e-9) / (median(author_values) + 1e-9)
    if e is not None and len(values) >= minimum:
        result["status"] = "partial_baseline" if "unknown_account_size" in result["warnings"] else "ok"
        result["engagement_percentile"] = percentile(e, values)
        med = median(values)
        mad = median(abs(x - med) for x in values)
        if mad > 0 and abs(e - med) > 6 * mad:
            result["warnings"].append("engagement_outlier_review_source")
        result["confidence_score"] = round(min(len(values) / 30, 1) * len(keys) / 4 * (.5 if "unknown_account_size" in result["warnings"] else 1), 3)
    result["confidence_definition"] = "Data coverage heuristic, not probability of virality or causality"
    return result
