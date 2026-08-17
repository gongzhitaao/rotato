"""Tag-driven batch rotation.

Rotate every secret whose note enrolls it (``#rotato=<type>``), dispatching each
to its rotator. Because enrollment lives in unvalidated free text where "off" is
silent, the run also reports its roster so a mistyped or dropped tag surfaces
instead of silently skipping rotation until the credential expires:

  * roster log   — what was rotated / skipped this run
  * STALE        — a tagged secret whose value is older than its cadence, i.e. a
                   rotation that has been silently failing (catches per-item
                   failures that recovered as well as ongoing ones)
  * UNTAGGED     — secrets with no ``#rotato`` tag, so a forgotten enrollment is
                   visible (roster diff)

STALE/UNTAGGED lines are shaped for log-based alert policies; a rotation that
fails this run makes the whole job exit non-zero (tripping the failure alert).
"""

import dataclasses
import datetime

from rotato import core, rotators, tags

# Per-secret override tag: max age (days) before the value is considered stale.
CADENCE_TAG = "cadence"
DEFAULT_STALE_AFTER_DAYS = 21.0


@dataclasses.dataclass
class Item:
    secret_id: str
    key: str
    type: str
    status: str  # "rotated" | "failed" | "unknown-type"
    detail: str = ""


@dataclasses.dataclass
class Report:
    rotated: list[Item] = dataclasses.field(default_factory=list)
    failed: list[Item] = dataclasses.field(default_factory=list)
    stale: list[str] = dataclasses.field(default_factory=list)
    untagged: list[str] = dataclasses.field(default_factory=list)


def _age_days(revision_date: str, now: datetime.datetime) -> float | None:
    if not revision_date:
        return None
    try:
        ts = datetime.datetime.fromisoformat(
            revision_date.replace("Z", "+00:00")
        )
    except ValueError:
        return None
    return (now - ts).total_seconds() / 86400.0


def rotate_tagged(
    store,
    secrets,
    now: datetime.datetime,
    default_stale_after_days: float = DEFAULT_STALE_AFTER_DAYS,
) -> Report:
    """Rotate every tagged secret; never let one failure abort the batch."""
    report = Report()
    for s in secrets:
        parsed = tags.parse(s.note)
        rtype = tags.rotator_type(parsed)
        if rtype is None:
            report.untagged.append(s.key)
            continue

        # Staleness uses the pre-rotation revision_date: if it is overdue coming
        # in, some previous run failed to rotate it (even if this run succeeds).
        stale_after = default_stale_after_days
        if CADENCE_TAG in parsed:
            try:
                stale_after = float(parsed[CADENCE_TAG])
            except ValueError:
                pass
        age = _age_days(s.revision_date, now)
        if age is not None and age > stale_after:
            report.stale.append(s.key)

        rotator = rotators.REGISTRY.get(rtype)
        if rotator is None:
            detail = f"no rotator {rtype!r}"
            report.failed.append(
                Item(s.id, s.key, rtype, "unknown-type", detail)
            )
            continue

        cfg = rotator.config(parsed)
        try:
            core.rotate_secret(
                store,
                s.id,
                lambda old, r=rotator, c=cfg: r.rotate(old, c),
            )
            report.rotated.append(Item(s.id, s.key, rtype, "rotated"))
        # A rotator may raise anything (HTTP, RotationError, KeyError, ...);
        # aggregate so one bad secret can't abort the batch.
        except Exception as exc:  # pylint: disable=broad-exception-caught
            report.failed.append(Item(s.id, s.key, rtype, "failed", repr(exc)))
    return report


def render(report: Report) -> int:
    """Print the roster for Cloud Logging; return the process exit code.

    STALE/UNTAGGED/FAILED lines carry stable prefixes so log-based alert
    policies can match them. Exit is non-zero only when a rotation failed this
    run, so a failed execution trips the existing job-failure alert.
    """
    rotated = ", ".join(f"{i.key}({i.type})" for i in report.rotated)
    print(f"roster: rotated {len(report.rotated)} [{rotated}]")

    for key in report.untagged:
        print(f"rotato-diff UNTAGGED {key}")
    for key in report.stale:
        print(f"rotato-alert STALE {key}")
    for item in report.failed:
        print(f"rotato-alert FAILED {item.key} ({item.type}): {item.detail}")

    return 1 if report.failed else 0
