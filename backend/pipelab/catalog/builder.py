"""Catalog builder subprocess: describes every element factory as JSON lines.

Run as ``python -m pipelab.catalog.builder``. It instantiates elements, which
may crash or hang in a broken plugin, so the parent (``build.py``) watches it
and restarts it past the offending element.

stdout protocol, one JSON object per line::

    {"event": "total", "count": 1500}
    {"event": "begin", "name": "videotestsrc"}
    {"event": "element", "data": {...ElementInfo...}}
    {"event": "done"}
"""

from __future__ import annotations

import argparse
import json
import sys

from pipelab.catalog.introspect import describe_factory
from pipelab.gst import Gst


def element_factories() -> list[Gst.ElementFactory]:
    features = Gst.Registry.get().get_feature_list(Gst.ElementFactory)
    return sorted(features, key=lambda factory: factory.get_name())


def _emit(event: dict) -> None:
    sys.stdout.write(json.dumps(event) + "\n")
    sys.stdout.flush()


def _describe(factory: Gst.ElementFactory, instantiate: bool) -> dict | None:
    for attempt_instantiate in (instantiate, False) if instantiate else (False,):
        try:
            return describe_factory(factory, attempt_instantiate).model_dump()
        except Exception:  # noqa: BLE001 - fall back to a description without instance
            continue
    return None


def run(after: str | None, no_instantiate: set[str]) -> None:
    factories = element_factories()
    _emit({"event": "total", "count": len(factories)})
    names = [factory.get_name() for factory in factories]
    start = names.index(after) + 1 if after in names else 0
    for factory in factories[start:]:
        name = factory.get_name()
        _emit({"event": "begin", "name": name})
        data = _describe(factory, instantiate=name not in no_instantiate)
        if data is not None:
            _emit({"event": "element", "data": data})
    _emit({"event": "done"})


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--after", default=None, help="resume after this factory")
    parser.add_argument("--no-instantiate", default="", help="comma separated factories")
    args = parser.parse_args(argv)
    run(args.after, {n for n in args.no_instantiate.split(",") if n})


if __name__ == "__main__":
    main()
