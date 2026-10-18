"""Remove entities whose value the BMS no longer sends, but only right after a (re)load.

A single poll can miss a status byte or a whole settings group. Removing the entity
then would delete the user's entity from the registry, and the next poll would create
it again. So after a load the first CLEANUP_ROUNDS complete read
rounds are watched, and only an entity missing in all of them is removed. The count
lives in memory: the next reload or restart watches again.
"""

CLEANUP_ROUNDS = 5


class StaleEntityWatch:
    """Counts complete read rounds per scope, for example the status bits of pack 1."""

    def __init__(self, rounds=CLEANUP_ROUNDS):
        self.rounds = rounds
        self._last_round = {}
        self._counted = {}
        self._missing = {}
        self._decided = set()

    def complete_round(self, scope, round_id, candidates, present):
        """Count one complete round and return the unique ids to remove.

        candidates are the unique ids of this scope in the entity registry, present the
        ones whose value this round delivered. round_id stops the same poll from counting
        twice. The answer is empty until the last watched round, and empty afterwards.
        """
        if scope in self._decided or self._last_round.get(scope) == round_id:
            return set()
        self._last_round[scope] = round_id
        for unique_id in candidates:
            self._missing[unique_id] = 0 if unique_id in present else self._missing.get(unique_id, 0) + 1
        self._counted[scope] = self._counted.get(scope, 0) + 1
        if self._counted[scope] < self.rounds:
            return set()
        self._decided.add(scope)
        return {unique_id for unique_id in candidates if self._missing.get(unique_id, 0) >= self.rounds}


def pack_is_fresh(data, kind, pack_id):
    """True when this poll read the pack's analog or warning frame, not the cached copy."""
    fresh = (data or {}).get("fresh")
    if fresh is None:
        return True
    return pack_id in fresh.get(kind, ())


def remove_stale(registry, watch, scope, round_id, candidates, present):
    """Feed one round to the watch and remove what it names.

    candidates maps unique id to entity id. Returns the removed unique ids.
    """
    removed = watch.complete_round(scope, round_id, set(candidates), present)
    for unique_id in removed:
        registry.async_remove(candidates[unique_id])
    return removed
