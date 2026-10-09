# Upstream source

- Project: BD2 Fishing by MadestSamurai (Bilibili: MadSamurai)
- Source: https://github.com/MadestSamurai/bd2-fishing
- Version: 0.4.5
- Commit: d4821c71192e63ebbb5dcc56644c973470a3d1d8
- License: MIT; see LICENSE and THIRD_PARTY_NOTICES.md, plus licenses/.

The core, compatibility resolver, runtime hook, IPC, shared policies, localization,
vendored injector, and offline tests are retained as source. The original WPF
desktop application is retained only as a localization regression fixture; it is
not built, launched or used by YES-BD2.

Local adaptations:
- FishingConnection accepts an explicit PID and process start time, validates the
  game name and Windows session, and rejects stale or cross-session processes.
- FishingIdentity uses a YES-BD2 data directory separated by Windows session.
- The language catalogs include the two new process-selection error messages.

YES-BD2's bridge is in tools/fishing and its Python task is src/tasks/FishingTask.py.
The optional feature injects a runtime into the game; it is not image recognition.
No game assemblies or resources are distributed here.
