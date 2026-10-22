"""Validate synthetic PA-04 contract cases and optionally write a private bundle."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from clasor_agents.pa04.package import build
from clasor_agents.pa04.contract import ROOT, canonical


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path)
    args = parser.parse_args()
    result = build()
    recorded = json.loads((ROOT / 'manifest.json').read_text())
    if result != recorded:
        raise SystemExit('FAIL: contract manifest drift; review changes and rebuild manifest')
    if args.bundle:
        args.bundle.parent.mkdir(parents=True,exist_ok=True)
        args.bundle.write_text(canonical(dict(manifest=result,
            input_schema=json.loads((ROOT/'schemas/input.schema.json').read_text()),
            output_schema=json.loads((ROOT/'schemas/output.schema.json').read_text()),
            cases=json.loads((ROOT/'fixtures/cases.json').read_text())))+'\n')
    print('PA-04: 4 synthetic contract cases passed; no model or runtime invoked.')


if __name__ == '__main__':
    main()
