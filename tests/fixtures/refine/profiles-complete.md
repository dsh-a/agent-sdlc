# Customer profiles — example app

Four profiles. `/refine`'s `profile-impact` probe reads `Breaks when`.

## The Builder

- Goal: add load week over week against a fixed program.
- Session shape: 60–90 min, 5–7 movements, every set logged while resting.
- Data volume: heaviest in the product — thousands of sets within a year.
- Breaks when: a list is paginated at a size tuned for a light user, or history
  loads eagerly.

## The Resolutioner

- Goal: start, and not feel behind on day three.
- Session shape: 20–30 min, twice a week, abandons by week five.
- Data volume: near-empty for the whole time they are present.
- Breaks when: a screen's first run is an empty state with nothing to do, or
  onboarding assumes a program already exists.

## The Socialite

- Goal: be seen training with people they know.
- Session shape: irregular, driven by who else is going.
- Data volume: sparse and bursty.
- Breaks when: a flow cannot be completed without a full prior history, or
  sharing requires a complete profile.

## The Runner

- Goal: keep lifting as support for a mileage plan they track elsewhere.
- Session shape: 25 min, twice weekly, same six movements.
- Data volume: narrow and deep — few movements, long series.
- Breaks when: the product assumes it owns the training plan, or a weekly view
  hides a two-day-a-week pattern.

## A note on these profiles

Prose, not a profile: it carries none of the four fields. The first real profile file opened with
two sections like this one and both were counted as profiles with no fields.
