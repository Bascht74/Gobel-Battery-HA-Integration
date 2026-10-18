"""Remove the entities of the settings mode that is not active.

With changeable settings on, numbers, switches and selects replace the
read-only setting sensors and status flags. Turning the option on or off
would otherwise leave the replaced entities behind as unavailable.
"""

from .pace_config import FIELDS

# Setting sensors that a number or select replaces. Read-only values are not here.
REPLACED_SETTINGS = frozenset({field["key"] for field in FIELDS} | {"limiter_gear"})

# Status flags (binary sensors) that a switch replaces.
REPLACED_FLAGS = frozenset(
    {
        "instruction_state_status_charge_enabled",
        "instruction_state_status_discharge_enabled",
        "instruction_state_status_current_limit_enabled",
        "control_state_buzzer_warn_function",
        "control_state_led_warn_function",
    }
)


def stale_unique_ids(entry_id, unique_ids, changeable, owns_configuration):
    """Unique ids of this entry that belong to the other mode."""
    prefix = f"{entry_id}_pack_"
    stale = set()
    for unique_id in unique_ids:
        if not unique_id or not unique_id.startswith(prefix):
            continue
        pack, _, metric = unique_id[len(prefix):].partition("_")
        if changeable:
            replaced = metric in REPLACED_SETTINGS or metric in REPLACED_FLAGS
            if replaced and pack.isdigit() and owns_configuration(int(pack)):
                stale.add(unique_id)
        elif metric.startswith("expert_"):
            stale.add(unique_id)
    return stale
