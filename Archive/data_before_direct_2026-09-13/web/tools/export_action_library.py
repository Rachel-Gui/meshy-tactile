"""Export current reviewed XLSX clips for browser playback. Run with numpy/matplotlib installed."""
from pathlib import Path
import importlib.util
import json
import math
import os
import sys
import tempfile

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'tactile-matplotlib'))
ROOT = Path(__file__).resolve().parents[2]
source = ROOT / 'tools/viewers/view_all_heatmaps.py'
spec = importlib.util.spec_from_file_location('action_heatmaps', source)
viewer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = viewer
spec.loader.exec_module(viewer)
OUT = ROOT / 'web/public/action-library'
OUT.mkdir(parents=True, exist_ok=True)
manifest = []
for group, entries in viewer.discover_entries().items():
    for entry in entries:
        data = viewer.load_entry(entry)
        robot = entry.kind == '132_segment'
        sparse = entry.kind not in ['96_segment', '132_segment']
        count = 132 if robot else 18 if sparse else 96
        dataset_id = entry.kind + '_' + entry.action_id
        def matrix(key):
            value = data[key]
            return None if value is None else [[round(float(v), 6) if math.isfinite(v) else None for v in row] for row in value.reshape(len(value), count)]
        times = data['action_time']
        record = {
            'id': dataset_id, 'label': f'{entry.action_id} · {entry.action_type}',
            'group': group, 'action': entry.action_type, 'sensorCount': count,
            'source': str(entry.path.resolve().relative_to(ROOT)), 'originalFrames': data['original_frame_count'],
            'fps': 20, 'interpolated': data.get('display_interpolated', False),
            'labels': data['labels'].reshape(-1).tolist(),
            'coordinates': ([{'row': i // 12 + 1, 'column': i % 12 + 1} for i in range(132)] if robot else
                            [{'row': (col + slot) % 6 + 1, 'column': col + 1}
                             for slot in range(3) for col in range(6)] if sparse else
                            [{'row': i // 8 + 1, 'column': i % 8 + 1} for i in range(96)]),
            'times': [round(t-times[0], 6) for t in times],
            'signal': matrix('signal'), 'raw': matrix('raw'), 'baseline': matrix('baseline'),
        }
        (OUT / f'{dataset_id}.json').write_text(json.dumps(record, ensure_ascii=False, allow_nan=False, separators=(',', ':'))+'\n')
        manifest.append({k: record[k] for k in ['id','label','group','action','sensorCount','source','originalFrames']}
                        | {'url': f'/action-library/{dataset_id}.json', 'frames':len(times)})
(OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(f'Exported {len(manifest)} reviewed actions to {OUT}')
