"""Build or verify the PA-04 credential-free DSL and matching prompt manifest."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from clasor_agents.pa04.contract import ROOT,canonical
from clasor_agents.pa04.workflow import build,manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    artifacts={ROOT/'workflow.json':build(),ROOT/'workflow-manifest.json':manifest()}
    for path,value in artifacts.items():
        if args.check:
            if json.loads(path.read_text())!=value:raise SystemExit('FAIL: workflow or prompt drift')
        else:path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    print('PA-04 Workflow/prompt artifacts match; no runtime invoked.')


if __name__=='__main__':main()
