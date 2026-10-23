"""Build/check the credential-free TL Workflow and matching prompt manifest."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from clasor_agents.tl_planner.contract import ROOT
from clasor_agents.tl_planner.workflow import build, manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    for name,value in {'workflow.json':build(),'workflow-manifest.json':manifest()}.items():
        path=ROOT/name
        if args.check:
            if json.loads(path.read_text()) != value:
                raise SystemExit('FAIL: TL workflow or prompt drift')
        else:
            path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print('TL Workflow/prompt artifacts match; no runtime invoked.')


if __name__=='__main__':main()
