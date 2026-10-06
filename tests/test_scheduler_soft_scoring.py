import unittest

from scheduler.engine import (
    base_soft_score,
    dynamic_soft_score,
    projected_daily_load_penalty,
    projected_gap_penalty,
    projected_week_balance_penalty,
)


class SchedulerSoftScoringHelperTests(unittest.TestCase):
    def setUp(self):
        self.part = {
            "part_id": 10,
            "duration_slots": 1,
            "group_ids": {1},
            "staff_ids": {7},
        }
        self.other = {
            1: {"part_id": 1, "duration_slots": 1, "group_ids": {1}, "staff_ids": {7}},
            2: {"part_id": 2, "duration_slots": 1, "group_ids": {2}, "staff_ids": {8}},
            3: {"part_id": 3, "duration_slots": 1, "group_ids": {1}, "staff_ids": {9}},
            4: {"part_id": 4, "duration_slots": 1, "group_ids": {1}, "staff_ids": {9}},
            5: {"part_id": 5, "duration_slots": 1, "group_ids": {1}, "staff_ids": {9}},
        }

    def test_group_gap_prefers_adjacent_over_separated_placement(self):
        assignments = {1: {"day": "Monday", "start_period": 1}}
        adjacent = {"day": "Monday", "start_period": 2}
        separated = {"day": "Monday", "start_period": 5}
        self.assertLess(
            projected_gap_penalty(self.part, adjacent, assignments, self.other, "group_ids"),
            projected_gap_penalty(self.part, separated, assignments, self.other, "group_ids"),
        )

    def test_staff_gap_prefers_adjacent_over_separated_placement(self):
        assignments = {1: {"day": "Monday", "start_period": 1}}
        adjacent = {"day": "Monday", "start_period": 2}
        separated = {"day": "Monday", "start_period": 6}
        self.assertLess(
            projected_gap_penalty(self.part, adjacent, assignments, self.other, "staff_ids"),
            projected_gap_penalty(self.part, separated, assignments, self.other, "staff_ids"),
        )

    def test_two_period_class_has_no_internal_gap(self):
        long_part = dict(self.part, duration_slots=2)
        assignments = {1: {"day": "Monday", "start_period": 1}}
        placement = {"day": "Monday", "start_period": 2}
        self.assertEqual(
            projected_gap_penalty(long_part, placement, assignments, self.other, "group_ids"),
            0,
        )

    def test_unrelated_entities_do_not_change_gap_penalty(self):
        placement = {"day": "Monday", "start_period": 5}
        unrelated = {2: {"day": "Monday", "start_period": 1}}
        self.assertEqual(
            projected_gap_penalty(self.part, placement, unrelated, self.other, "group_ids"),
            projected_gap_penalty(self.part, placement, {}, self.other, "group_ids"),
        )

    def test_daily_load_penalty_prefers_lighter_day(self):
        assignments = {
            1: {"day": "Monday", "start_period": 1},
            3: {"day": "Monday", "start_period": 3},
            4: {"day": "Monday", "start_period": 5},
            5: {"day": "Monday", "start_period": 7},
        }
        monday = {"day": "Monday", "start_period": 9}
        tuesday = {"day": "Tuesday", "start_period": 9}
        self.assertGreater(
            projected_daily_load_penalty(self.part, monday, assignments, self.other),
            projected_daily_load_penalty(self.part, tuesday, assignments, self.other),
        )

    def test_week_balance_prefers_underused_day(self):
        assignments = {
            1: {"day": "Monday", "start_period": 1},
            3: {"day": "Monday", "start_period": 3},
            4: {"day": "Tuesday", "start_period": 5},
            5: {"day": "Tuesday", "start_period": 7},
        }
        monday = {"day": "Monday", "start_period": 9}
        wednesday = {"day": "Wednesday", "start_period": 9}
        self.assertGreater(
            projected_week_balance_penalty(self.part, monday, assignments, self.other),
            projected_week_balance_penalty(self.part, wednesday, assignments, self.other),
        )


class SchedulerSoftRankingTests(unittest.TestCase):
    def _part(self, **overrides):
        part = {
            "part_id": 10,
            "session_id": 10,
            "module_id": 100,
            "duration_slots": 1,
            "expected_students": 40,
            "faculty_id": 1,
            "group_ids": {1},
            "staff_ids": {7},
        }
        part.update(overrides)
        return part

    def _room(self, room_id, capacity, faculty_id=1):
        return {
            "room_id": room_id,
            "capacity": capacity,
            "faculty_id": faculty_id,
            "is_shared": 0,
        }

    def test_smaller_legal_room_beats_much_larger_room(self):
        part = self._part()
        small = base_soft_score(part, [self._room(1, 50)], "Tuesday", 4)
        large = base_soft_score(part, [self._room(2, 200)], "Tuesday", 4)
        self.assertLess(small, large)

    def test_same_faculty_room_beats_cross_faculty_when_capacity_is_comparable(self):
        part = self._part()
        home = base_soft_score(part, [self._room(1, 55, faculty_id=1)], "Tuesday", 4)
        away = base_soft_score(part, [self._room(2, 50, faculty_id=2)], "Tuesday", 4)
        self.assertLess(home, away)

    def test_repeated_module_prefers_wednesday_spacing_after_monday(self):
        part = self._part()
        other = self._part(part_id=1, session_id=1)
        by_id = {1: other}
        assignments = {1: {"day": "Monday", "start_period": 3, "room_ids": {1}}}
        same_day = {"day": "Monday", "start_period": 6, "base_score": 0.0, "room_ids": {2}}
        wednesday = {"day": "Wednesday", "start_period": 6, "base_score": 0.0, "room_ids": {2}}
        self.assertGreater(
            dynamic_soft_score(part, same_day, assignments, by_id),
            dynamic_soft_score(part, wednesday, assignments, by_id),
        )

    def test_edge_period_penalties_remain_positive(self):
        part = self._part()
        middle = base_soft_score(part, [self._room(1, 50)], "Tuesday", 5)
        first = base_soft_score(part, [self._room(1, 50)], "Tuesday", 1)
        last = base_soft_score(part, [self._room(1, 50)], "Tuesday", 10)
        self.assertGreater(first, middle)
        self.assertGreater(last, middle)

    def test_dynamic_score_uses_student_gap_penalty(self):
        part = self._part(module_id=200)
        other = self._part(part_id=1, module_id=100)
        by_id = {1: other}
        assignments = {1: {"day": "Monday", "start_period": 1, "room_ids": {1}}}
        adjacent = {"day": "Monday", "start_period": 2, "base_score": 0.0, "room_ids": {2}}
        separated = {"day": "Monday", "start_period": 6, "base_score": 0.0, "room_ids": {2}}
        self.assertLess(
            dynamic_soft_score(part, adjacent, assignments, by_id),
            dynamic_soft_score(part, separated, assignments, by_id),
        )

    def test_dynamic_score_uses_lecturer_gap_penalty(self):
        part = self._part(module_id=200, group_ids={99}, staff_ids={7})
        other = self._part(part_id=1, module_id=100, group_ids={1}, staff_ids={7})
        by_id = {1: other}
        assignments = {1: {"day": "Monday", "start_period": 1, "room_ids": {1}}}
        adjacent = {"day": "Monday", "start_period": 2, "base_score": 0.0, "room_ids": {2}}
        separated = {"day": "Monday", "start_period": 7, "base_score": 0.0, "room_ids": {2}}
        self.assertLess(
            dynamic_soft_score(part, adjacent, assignments, by_id),
            dynamic_soft_score(part, separated, assignments, by_id),
        )


if __name__ == "__main__":
    unittest.main()
