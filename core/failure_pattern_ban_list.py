from collections import defaultdict
from typing import Dict, List, Optional, Tuple
import random
import time

# Maximum number of failure entries to track per domain
MAX_FAILURES_PER_DOMAIN = 20

# Ban threshold: number of consecutive failures before banning
BAN_THRESHOLD = 3

# Ban duration in cycles
BAN_DURATION_CYCLES = 5

# Probability of re-allowing a domain after ban expires
RE_ALLOW_PROBABILITY = 0.5


class FailurePatternBanList:
    """
    Tracks mutation failure patterns per domain and implements a ban/allow mechanism
    to avoid repeatedly attempting mutations on problematic domains.
    """

    def __init__(self):
        # Structure: {domain: [list of failure timestamps or cycle numbers]}
        self._failures: Dict[str, List[int]] = defaultdict(list)
        # Structure: {domain: ban_end_cycle}  (None if not banned)
        self._bans: Dict[str, Optional[int]] = {}
        # Current cycle counter (incremented externally or by the orchestrator)
        self._current_cycle: int = 0

    def set_current_cycle(self, cycle: int) -> None:
        """Set the current cycle number for ban expiry calculations."""
        self._current_cycle = cycle

    def record_failure(self, domain: str, cycle: Optional[int] = None) -> None:
        """
        Record a mutation failure for a given domain.
        If the domain is already banned, this does nothing (failures during ban don't count).
        """
        if cycle is None:
            cycle = self._current_cycle

        # Do not record failures if domain is currently banned
        if self.is_banned(domain):
            return

        failures = self._failures[domain]
        failures.append(cycle)

        # Trim to max size
        if len(failures) > MAX_FAILURES_PER_DOMAIN:
            self._failures[domain] = failures[-MAX_FAILURES_PER_DOMAIN:]

        # Check for consecutive failures
        consecutive = self._get_consecutive_failures(domain)
        if consecutive >= BAN_THRESHOLD:
            self._ban_domain(domain)

    def _get_consecutive_failures(self, domain: str) -> int:
        """
        Count consecutive failures for a domain by looking at the most recent failures
        and checking if they occurred in sequence (each within the same or next cycle).
        """
        failures = self._failures.get(domain, [])
        if not failures:
            return 0

        # Count from the end backwards while failures are consecutive
        count = 1
        for i in range(len(failures) - 2, -1, -1):
            # Consider consecutive if the cycle difference is <= 1
            if failures[i + 1] - failures[i] <= 1:
                count += 1
            else:
                break
        return count

    def _ban_domain(self, domain: str) -> None:
        """Ban a domain for BAN_DURATION_CYCLES cycles."""
        ban_end = self._current_cycle + BAN_DURATION_CYCLES
        self._bans[domain] = ban_end

    def is_banned(self, domain: str) -> bool:
        """Check if a domain is currently banned."""
        ban_end = self._bans.get(domain)
        if ban_end is None:
            return False
        if self._current_cycle >= ban_end:
            # Ban expired, remove it
            del self._bans[domain]
            return False
        return True

    def attempt_re_allow(self, domain: str) -> bool:
        """
        Attempt to re-allow a domain after its ban has expired.
        Returns True if the domain is now allowed (either it was never banned,
        ban expired and re-allowed, or ban expired and not re-allowed but we
        keep it banned until next check).
        """
        if not self.is_banned(domain):
            return True  # Not banned, so allowed

        # Ban is still active
        ban_end = self._bans.get(domain)
        if ban_end is None:
            return True

        if self._current_cycle >= ban_end:
            # Ban expired, decide whether to re-allow
            if random.random() < RE_ALLOW_PROBABILITY:
                # Re-allow: remove ban and clear failure history for this domain
                del self._bans[domain]
                self._failures[domain] = []
                return True
            else:
                # Extend ban for another BAN_DURATION_CYCLES
                self._bans[domain] = self._current_cycle + BAN_DURATION_CYCLES
                return False
        else:
            return False

    def get_allowed_domains(self, domains: List[str]) -> List[str]:
        """
        Filter a list of domains, returning only those that are allowed
        (not banned or re-allowed after ban expiry).
        """
        allowed = []
        for domain in domains:
            if self.attempt_re_allow(domain):
                allowed.append(domain)
        return allowed

    def get_banned_domains(self) -> List[str]:
        """Return list of currently banned domains."""
        return [d for d, end in self._bans.items() if self._current_cycle < end]

    def get_failure_count(self, domain: str) -> int:
        """Get the number of recorded failures for a domain."""
        return len(self._failures.get(domain, []))

    def get_consecutive_failure_count(self, domain: str) -> int:
        """Get the number of consecutive failures for a domain."""
        return self._get_consecutive_failures(domain)

    def clear_domain(self, domain: str) -> None:
        """Clear all failure records and ban status for a domain."""
        self._failures.pop(domain, None)
        self._bans.pop(domain, None)

    def reset(self) -> None:
        """Reset all tracking data."""
        self._failures.clear()
        self._bans.clear()
        self._current_cycle = 0

    def get_state(self) -> dict:
        """Return serializable state for debugging or persistence."""
        return {
            "current_cycle": self._current_cycle,
            "failures": {k: list(v) for k, v in self._failures.items()},
            "bans": {k: v for k, v in self._bans.items() if v is not None},
        }

    def adjust_probabilities(self, base_probabilities: Dict[str, float]) -> Dict[str, float]:
        """
        Given a dictionary of domain -> base probability, adjust probabilities
        by zeroing out banned domains and redistributing their probability mass
        among allowed domains.
        """
        allowed = self.get_allowed_domains(list(base_probabilities.keys()))
        if not allowed:
            # If no domains allowed, return original (should not happen in practice)
            return base_probabilities

        banned_mass = 0.0
        adjusted = {}
        for domain, prob in base_probabilities.items():
            if domain in allowed:
                adjusted[domain] = prob
            else:
                banned_mass += prob
                adjusted[domain] = 0.0

        # Redistribute banned mass among allowed domains
        if banned_mass > 0 and allowed:
            redistribution = banned_mass / len(allowed)
            for domain in allowed:
                adjusted[domain] += redistribution

        return adjusted