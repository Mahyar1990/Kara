"""Build/check offline PA-04 -> TL mapping; never call Kara or an LLM."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from clasor_agents.product_flow.flow import ROOT, template, manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    for name,value in {'flow-template.json':template(),'manifest.json':manifest()}.items():
        path=ROOT/name
        if args.check:
            if json.loads(path.read_text())!=value: raise SystemExit('FAIL: flow mapping drift')
        else:path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print('Flow mapping/preflight artifacts match; no runtime invoked.')


if __name__=='__main__':main()
