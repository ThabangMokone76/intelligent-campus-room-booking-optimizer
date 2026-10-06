CONTINUOUS = "CONTINUOUS"
SPLIT = "SPLIT"


def normalise_session_type(value):
    return "" if value is None else str(value).strip().lower()


def split_eligible(session):
    return (
        normalise_session_type(session.get("session_type")) == "lecture"
        and int(session.get("duration_slots", 0)) == 2
        and bool(session.get("can_split_duration", 0))
    )


def legal_representation(session, representation_type):
    stype = normalise_session_type(session.get("session_type"))
    duration = int(session.get("duration_slots", 0))
    if representation_type == CONTINUOUS:
        return duration in (1, 2)
    if representation_type == SPLIT:
        return split_eligible(session)
    return False


def split_siblings(part_a, part_b):
    return (
        part_a.get("session_id") == part_b.get("session_id")
        and part_a.get("representation_type") == SPLIT
        and part_b.get("representation_type") == SPLIT
        and part_a.get("part_id") != part_b.get("part_id")
    )


def split_sibling_day_conflict(part_a, placement_a, part_b, placement_b):
    return split_siblings(part_a, part_b) and placement_a.get("day") == placement_b.get("day")
