#!/usr/bin/env python3
"""Consolidate duplicate Siren Test events into one per date.

Background: prior to the fix in app/admin/routes.py _create_siren_test_event,
recording each siren result via the admin form created its own Event row.
A monthly siren test where 7 volunteers each tested a different siren
produced 7 separate events on the same date — but conceptually it was
one event with 7 attendees. This script finds those duplicates and
consolidates them: for each date that has more than one Siren Test
event, it keeps the lowest-id event, moves any unique attendance from
the duplicates onto it, and deletes the dupes.

Run from the project root (or /opt/sirentracker on the server):
    .venv/bin/python scripts/dedupe_siren_test_events.py            # dry run
    .venv/bin/python scripts/dedupe_siren_test_events.py --apply    # actually delete

The dry run prints exactly what it would do so you can sanity-check
before flipping the switch. Always run a dry run first.
"""
import os
import sys
from collections import defaultdict

# Allow `python scripts/dedupe_siren_test_events.py` from the project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.extensions import db
from app.models import Event, EventAttendance  # noqa: F401 (needed for cascade ORM lookups)


def main():
    apply = '--apply' in sys.argv
    config = 'production' if '--prod' in sys.argv else None

    app = create_app(config)
    with app.app_context():
        # Pull every Siren Test event grouped by date
        rows = (
            db.session.query(Event)
            .filter(Event.event_type == 'Siren Test',
                    Event.category == 'Siren Test')
            .order_by(Event.date, Event.id)
            .all()
        )
        by_date = defaultdict(list)
        for ev in rows:
            by_date[ev.date].append(ev)

        dupe_groups = {d: evs for d, evs in by_date.items() if len(evs) > 1}

        if not dupe_groups:
            print('No duplicate Siren Test events found. Nothing to do.')
            return 0

        total_to_delete = 0
        total_attendance_moved = 0
        total_attendance_dropped = 0

        for test_date, events in sorted(dupe_groups.items()):
            keeper = events[0]  # lowest id wins
            dupes = events[1:]
            print(f'\n{test_date}: keeping event {keeper.id} '
                  f'("{keeper.description}"), '
                  f'merging in {len(dupes)} duplicate(s)')

            # Members already attending the keeper — we can't double-add them
            # because (event_id, member_id) is uniquely constrained.
            keeper_member_ids = {a.member_id for a in keeper.attendance}

            for dupe in dupes:
                print(f'  -> merge event {dupe.id} ("{dupe.description}")')
                # Iterate over a copy because we mutate the collection in-place.
                for att in list(dupe.attendance):
                    if att.member_id in keeper_member_ids:
                        # Already on the keeper — drop the dupe row
                        print(f'     - discard duplicate attendance for member {att.member_id}')
                        total_attendance_dropped += 1
                        if apply:
                            dupe.attendance.remove(att)
                            db.session.delete(att)
                    else:
                        # Move it to the keeper. Use the ORM collections (not
                        # raw att.event_id = ...) so when we delete the dupe
                        # below, its cascade='all, delete-orphan' doesn't take
                        # the attendance with it.
                        print(f'     - reassign attendance for member {att.member_id} '
                              f'({att.hours}h) -> event {keeper.id}')
                        keeper_member_ids.add(att.member_id)
                        total_attendance_moved += 1
                        if apply:
                            dupe.attendance.remove(att)
                            keeper.attendance.append(att)

                if apply:
                    db.session.flush()
                    db.session.delete(dupe)

                total_to_delete += 1

        print(f'\nSummary: {total_to_delete} duplicate event(s) across '
              f'{len(dupe_groups)} date(s) would be removed. '
              f'{total_attendance_moved} attendance row(s) reassigned, '
              f'{total_attendance_dropped} discarded as already-present.')

        if apply:
            db.session.commit()
            print('Applied. Database updated.')
            print('Tip: review the consolidated events in the admin UI and')
            print('     edit their descriptions if needed (e.g. "Monthly Siren Test").')
        else:
            print('\nDry run only — re-run with --apply to actually delete.')
        return 0


if __name__ == '__main__':
    raise SystemExit(main())
