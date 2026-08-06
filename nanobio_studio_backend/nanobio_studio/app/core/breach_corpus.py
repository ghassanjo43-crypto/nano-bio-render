"""Optional check of a password against a local breach corpus.

The decision this file records
------------------------------
The embedded common-password list is **sufficient for initial deployment of
this platform, and not sufficient in general.** The difference is who gets
accounts.

This is not a public sign-up service. Accounts are created by an administrator
for a named colleague at a named organization, the population is in the tens,
and every account already passes a 12-character minimum, a normalised-base
check that defeats the digit-suffix trick, a sequence check and an
identity-substring check. The realistic attack is credential stuffing with a
password reused from somewhere else — and against a hundred accounts with an
attempt limiter in front of them, the marginal accounts caught by a full
600-million-entry corpus over the embedded list is small.

What makes it *acceptable* rather than merely convenient is that the gap is
bounded and the fix is a configuration change, not a rewrite. So:

* **Deployed as-is**, the embedded list applies. Recorded as a stated
  limitation, not a silent one.
* **Set ``PASSWORD_BREACH_CORPUS_PATH``** and every new password is additionally
  checked against a downloaded corpus. Required before this platform is opened
  to self-registration or grows past a small named population, and that
  condition is written into the settings documentation rather than left to
  memory.

Why a local file and not the HaveIBeenPwned API
-----------------------------------------------
k-anonymity makes the range API safe in the sense that the full hash never
leaves — but it still sends the first five hex characters of a hash of a
password belonging to a named researcher to a third party, from a regulated
platform, on a path an operator would have to justify in a data-protection
assessment. It also puts a network call, with its timeouts and outages, inside
password setting: the corpus being unreachable would either block people from
activating accounts or silently skip the check, and both are worse than the
embedded list.

A downloaded corpus file has neither problem. It is read with a binary search
over the sorted file — no network, no third party, constant memory regardless
of corpus size, so the full 600-million-entry download works on a small
instance.

Format
------
The HIBP ``pwned-passwords-sha1-ordered-by-hash`` download, unmodified:
uppercase SHA-1, a colon, an occurrence count, one per line, sorted by hash.
Sorted order is what the search depends on; ``verify_corpus()`` checks it on a
sample at startup rather than trusting the filename.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

__all__ = ["BreachCorpus", "CorpusUnusable", "load_corpus", "corpus_status"]

#: Width at which bisection stops and a forward scan takes over. Small enough
#: that the scan is one disk read, large enough that the bisection's final
#: off-by-one-line cases never arise.
_LINEAR_SCAN_BYTES = 8192

#: Generous upper bound on one corpus line ("40 hex : count").
_MAX_LINE_BYTES = 128


def _occurrences(count: str) -> int:
    """A malformed count is treated as disqualifying rather than ignored.

    The hash matched; only the occurrence figure is unreadable. Treating that
    as "seen zero times" would let a corrupt line silently admit a password
    that is definitely in the corpus.
    """
    try:
        return int(count or 0)
    except ValueError:
        return MIN_OCCURRENCES + 1


#: An entry seen this many times or fewer is not treated as disqualifying.
#: A password appearing once in a decade-old aggregate corpus is a far weaker
#: signal than one appearing ten million times, and rejecting singletons pushes
#: users toward the shorter, more memorable passwords the corpus is full of.
MIN_OCCURRENCES = 10


class CorpusUnusable(RuntimeError):
    """The configured corpus cannot be searched, so it must not be claimed."""


@dataclass(frozen=True)
class CorpusHit:
    found: bool
    occurrences: int = 0


class BreachCorpus:
    """Binary search over a sorted hash file.

    Constant memory: the file is never loaded, only seeked. Each probe lands
    mid-file, scans forward to the next newline and compares — the usual
    line-oriented binary search, which costs about 30 seeks for a 40 GB file.
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.is_file():
            raise CorpusUnusable(
                f"the breach corpus {self.path} does not exist. Either "
                f"download it or unset PASSWORD_BREACH_CORPUS_PATH — a "
                f"configured-but-missing corpus would mean the check silently "
                f"does nothing while appearing to be enabled.")
        self.size = self.path.stat().st_size
        if self.size == 0:
            raise CorpusUnusable(f"the breach corpus {self.path} is empty")

    def _line_at(self, handle, offset: int) -> tuple[int, str]:
        """Return the start offset and text of the line containing ``offset``."""
        handle.seek(offset)
        if offset:
            handle.readline()  # discard the partial line
        start = handle.tell()
        return start, handle.readline().decode("ascii", "ignore").strip()

    def lookup(self, password: str) -> CorpusHit:
        """Narrow by bisection, then scan the last few kilobytes.

        The bisection alone is not enough, and the reason is worth stating
        because it is the classic way a line-oriented binary search goes wrong.
        A probe at byte ``middle`` lands mid-line, so it discards the partial
        line and reports the *next* one. Two different probes can therefore
        report the same line, and a bound set from that line's start does not
        move — the loop spins forever on a file it should search in thirty
        seeks.

        So both bounds are set from ``middle`` rather than from the line the
        probe happened to reach, which makes each step strictly narrower and
        guarantees termination. Bisection stops while the range is still a few
        kilobytes wide and a short forward scan finishes the job, which also
        removes the off-by-one-line question the bisection would otherwise
        have at its final step.

        Invariant: if the digest is in the file, its line begins at or after
        ``low``. ``low`` only ever advances to the start of a line whose hash
        sorts *before* the one being looked for.
        """
        digest = hashlib.sha1(  # noqa: S324 - the corpus format is SHA-1
            password.encode("utf-8")).hexdigest().upper()

        with self.path.open("rb") as handle:
            low, high = 0, self.size

            while high - low > _LINEAR_SCAN_BYTES:
                middle = (low + high) // 2
                start, line = self._line_at(handle, middle)
                if not line:
                    high = middle
                    continue

                candidate, _, count = line.partition(":")
                if candidate == digest:
                    return CorpusHit(found=True,
                                     occurrences=_occurrences(count))
                if candidate < digest:
                    # `start` is past `middle`, so this strictly advances.
                    low = start
                else:
                    # `middle` is strictly below `high` while low < high.
                    high = middle

            # Forward scan from a line boundary at or before the answer.
            handle.seek(low)
            if low:
                handle.readline()
            scanned = 0
            while scanned <= _LINEAR_SCAN_BYTES + _MAX_LINE_BYTES:
                raw = handle.readline()
                if not raw:
                    break
                scanned += len(raw)
                candidate, _, count = raw.decode(
                    "ascii", "ignore").strip().partition(":")
                if candidate == digest:
                    return CorpusHit(found=True,
                                     occurrences=_occurrences(count))
                if candidate > digest:
                    # Sorted file: everything after this is larger too.
                    break

        return CorpusHit(found=False)

    def is_compromised(self, password: str) -> tuple[bool, int]:
        hit = self.lookup(password)
        return (hit.found and hit.occurrences >= MIN_OCCURRENCES,
                hit.occurrences)

    def verify(self, samples: int = 64) -> dict:
        """Confirm the file is sorted and in the expected format.

        Sampling rather than a full scan: a full verification of a 40 GB file at
        every startup would add minutes to boot. Sixty-four ordered probes
        catch a wrong file, a wrong format and an unsorted one, which are the
        three ways this goes wrong in practice.
        """
        previous = ""
        checked = 0
        with self.path.open("rb") as handle:
            for index in range(samples):
                _start, line = self._line_at(
                    handle, (self.size * index) // samples)
                if not line:
                    continue
                candidate, _, count = line.partition(":")
                if len(candidate) != 40 or not all(
                        c in "0123456789ABCDEF" for c in candidate):
                    raise CorpusUnusable(
                        f"{self.path} line {index} is not an uppercase SHA-1 "
                        f"hash; expected the pwned-passwords "
                        f"ordered-by-hash format")
                if candidate < previous:
                    raise CorpusUnusable(
                        f"{self.path} is not sorted by hash at sample {index}. "
                        f"The lookup is a binary search and would return false "
                        f"negatives — silently passing compromised passwords.")
                previous = candidate
                checked += 1
        return {"samples_checked": checked, "bytes": self.size}


_corpus: BreachCorpus | None = None
_status: dict = {"configured": False, "active": False,
                 "reason": "no corpus configured"}


def load_corpus(path: str | os.PathLike | None) -> BreachCorpus | None:
    """Load and verify at startup. Raises rather than degrading quietly."""
    global _corpus, _status

    if not path:
        _corpus = None
        _status = {
            "configured": False, "active": False,
            "reason": "no corpus configured",
            "limitation": (
                "passwords are checked against the embedded common-password "
                "list only. Accepted for a small, administrator-provisioned "
                "population; set PASSWORD_BREACH_CORPUS_PATH before opening "
                "self-registration."),
        }
        return None

    corpus = BreachCorpus(Path(path))
    detail = corpus.verify()
    _corpus = corpus
    _status = {"configured": True, "active": True,
               "path": str(corpus.path.name), "min_occurrences": MIN_OCCURRENCES,
               **detail}
    return corpus


def active_corpus() -> BreachCorpus | None:
    return _corpus


def corpus_status() -> dict:
    """For the startup log and the diagnostics route. Never the corpus path in
    full — the directory layout of a production host is not diagnostics."""
    return dict(_status)
