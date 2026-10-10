# Changelog

These are internal development build numbers, **not yet GitHub releases**.

## v36 — Rear camera repair (player-tested working)

- Repositions hood rear-view camera behind the vehicle so the car no longer obstructs the view.
- Restores the forward hood position and rotation on release of `B`.
- Maintains the working `C` toggle and chase view.
- Preserves v35's visual rear-traffic retention.

## v35 — Visual rear traffic (player-tested working)

- Retains separate visual copies of cars as the normal traffic models recycle ahead.
- Uses correct Director Lingo local-variable slots.
- Removes an invalid `worldPosition` assignment and avoids reusing a gameplay difficulty property.
- No fixed artificial cap on retained visual copies.
- Preserves original traffic-recycling thresholds and near-player collision logic.

## v28 — Camera baseline (player-tested)

- Introduced the working `C` hood/chase camera toggle and hold-`B` look-back.
- Later v36 addressed rear-view obstruction and awkward hood-camera return.

## Other experiments

v27, v29–v34 were investigative builds. Several introduced script errors, unwanted camera movement, or traffic/difficulty regressions; they are not the recommended baseline. The published source tracks the v28 → v35 → v36 development chain.

## Still open

- Forward traffic appearing too close / popping in.
- Highway and environment visibly beginning near the horizon.
- Unusual audio behaviour while using the chase view.