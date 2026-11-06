#!/usr/bin/env python3
"""Plotting must preserve the registry, use separate metadata, and be deterministic."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    with tempfile.TemporaryDirectory(prefix='shogi-plot-test-') as name:
        out=Path(name);csv=out/'history.csv';registry=out/'history.json'
        csv.write_bytes((ROOT/'results/measurement-history.csv').read_bytes())
        registry.write_bytes((ROOT/'results/measurement-history.json').read_bytes())
        before=[digest(csv),digest(registry)]
        command=[sys.executable,str(ROOT/'scripts/plot-measurement-history.py'),'--input',str(csv),'--output',str(out/'history.svg')]
        subprocess.run(command,check=True,cwd=ROOT,capture_output=True)
        one=[digest(out/'history.svg'),digest(out/'history.png')]
        subprocess.run(command,check=True,cwd=ROOT,capture_output=True)
        assert before==[digest(csv),digest(registry)]
        assert one==[digest(out/'history.svg'),digest(out/'history.png')]
        assert isinstance(json.loads(registry.read_text()),list)
        assert (out/'history.plot.json').exists()
        bad=subprocess.run(command[:-1]+[str(registry)],cwd=ROOT,capture_output=True)
        assert bad.returncode and before==[digest(csv),digest(registry)]
        report={'passed':True,'measurement_data_unchanged':True,'separate_plot_metadata':True,
                'deterministic_svg_and_png':True,'invalid_output_path_rejected':True}
        print(json.dumps(report,indent=2))


if __name__=='__main__':main()
