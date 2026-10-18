"""Entities are removed only when their value stays away for 5 complete rounds after a (re)load.

The scenario: pack 1 has the status bits "short circuit" and "heater fault".
The user renamed "short circuit". One poll misses its byte. That must not remove the
entity. "heater fault" is never sent by this BMS, so that one goes.
"""

from custom_components.gobel_battery.stale_entities import CLEANUP_ROUNDS, StaleEntityWatch, pack_is_fresh

SHORT = "entry1_pack_1_protect_state_1_protect_short_circuit"
HEATER = "entry1_pack_1_fault_state_fault_heater"
BOTH = {SHORT, HEATER}


def test_five_rounds_are_watched():
    assert CLEANUP_ROUNDS == 5


def test_one_missed_poll_keeps_the_entity():
    watch = StaleEntityWatch()
    removed = set()
    # Poll 1 misses the short-circuit byte, polls 2 to 5 have it again.
    removed |= watch.complete_round("status_1", 1, BOTH, present=set())
    for poll in range(2, 6):
        removed |= watch.complete_round("status_1", poll, BOTH, present={SHORT})
    assert removed == {HEATER}


def test_value_missing_in_all_five_rounds_is_removed_after_the_fifth():
    watch = StaleEntityWatch()
    answers = [watch.complete_round("status_1", poll, BOTH, present={SHORT}) for poll in range(1, 6)]
    assert answers == [set(), set(), set(), set(), {HEATER}]


def test_nothing_is_removed_after_the_watched_rounds():
    # The short-circuit byte disappears an hour after the reload: the entity stays until the next reload.
    watch = StaleEntityWatch()
    for poll in range(1, 6):
        watch.complete_round("status_1", poll, BOTH, present=BOTH)
    later = [watch.complete_round("status_1", poll, BOTH, present=set()) for poll in range(6, 20)]
    assert all(answer == set() for answer in later)


def test_the_same_poll_counts_once():
    # Both platforms see each poll; a repeated poll number must not count as a new round.
    watch = StaleEntityWatch()
    for _repeat in range(10):
        assert watch.complete_round("status_1", 1, BOTH, present=set()) == set()


def test_a_pack_served_from_the_cache_is_not_a_round():
    data = {"fresh": {"analog": {0}, "warning": {0}}}
    assert pack_is_fresh(data, "warning", 0) is True
    assert pack_is_fresh(data, "warning", 1) is False
