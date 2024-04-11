#!/usr/bin/env python3

import argparse
import json
import shutil
import sys

from pathlib import Path
from vsd.specification import Specification

def main():
    parser = argparse.ArgumentParser("Modify components specification")
    parser.add_argument(
        "--spec-mod", type=Path, required=True, action="append",
        help="File with specification modifications",
    )
    parser.add_argument(
        "-s", "--spec", type=Path,
        default=Path("workspace/visual-system-designer-resources/components-specification.json"),
        help="Specification file",
    )
    args = parser.parse_args()

    if not args.spec.exists():
        print(f"error: {args.spec} doesn't exist.")
        sys.exit(1)

    if not all(p.exists() for p in args.spec_mod):
        print(f"error: Some of files: {', '.join(map(str, args.spec_mod))} don't exist.")
        sys.exit(1)

    old_spec_path = args.spec.with_suffix(".orig")
    shutil.copy(args.spec, old_spec_path)
    print(f"Saved original specification in {old_spec_path}")

    specification = Specification(args.spec)

    spec_mods = map(lambda p: json.load(open(p)), args.spec_mod)
    for mod in spec_mods:
        specification.modify(mod)

    with open(args.spec, "w") as f:
        json.dump(specification.spec_json, f, sort_keys=True, indent=4, ensure_ascii=False)


if __name__ == "__main__":
    main()
