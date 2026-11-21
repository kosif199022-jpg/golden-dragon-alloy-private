"""Acceptance tests for modeling3d_v23 (topics 18.01-18.10)."""
import ast
import base64
import json
import math
import struct
import unittest
from pathlib import Path

import modeling3d_v23 as M

FORBIDDEN_IMPORTS = {'subprocess', 'socket', 'urllib', 'http', 'shutil', 'os', 'sqlite3', 'ctypes'}
ALLOWED_IMPORTS = {'__future__', 'base64', 'hashlib', 'json', 'math', 'struct'}


class TestInterface(unittest.TestCase):
    def test_topics_and_ops(self):
        self.assertEqual(sorted(M.TOPICS), [f'18.{i:02d}' for i in range(1, 11)])
        self.assertEqual(list(M.TOPICS.values()),
                         ['machine_mesh', 'car_rig', 'cloth3d', 'camera3d', 'skinning', 'uv_atlas',
                          'area_lighting', 'export_mesh', 'lod_budget', 'cutaway'])
        self.assertEqual(set(M.TOPICS.values()), set(M.OPS))
        self.assertEqual(set(M.TOPIC_NAMES_AR), set(M.TOPICS))

    def test_run_all_defaults_json_deterministic(self):
        for op in M.OPS:
            with self.subTest(op=op):
                out = M.run(op, {})
                self.assertEqual(out['op'], op)
                self.assertEqual(set(out), {'op', 'result', 'assumptions', 'limits'})
                self.assertTrue(out['assumptions'] and out['limits'])
                self.assertTrue(all(isinstance(s, str) for s in out['assumptions'] + out['limits']))
                self.assertTrue(any('no GPU' in s and 'no Blender' in s for s in out['assumptions']))
                json.dumps(out, allow_nan=False)
                self.assertEqual(out, M.run(op, {}))

    def test_run_rejects_bad_input(self):
        bad = [
            ('nope', {}), ('car_rig', []), ('car_rig', {'zzz': 1}),
            ('car_rig', {f'k{i}': 1 for i in range(25)}),
            ('car_rig', {'steering_deg': True}), ('car_rig', {'steering_deg': float('nan')}),
            ('car_rig', {'steering_deg': 89}), ('car_rig', {'wheelbase': 0.5, 'track': 4.0,
                                                            'steering_deg': 60}),
            ('machine_mesh', {'parts': [{'name': 'a', 'shape': 'box', 'radius': 1}]}),
            ('machine_mesh', {'parts': [{'name': 'a'}, {'name': 'a'}]}),
            ('machine_mesh', {'parts': [{'name': 'a', 'shape': 'gear', 'outer_radius': 0.3,
                                         'root_radius': 0.4}]}),
            ('machine_mesh', {'parts': [{'name': 'a'}, {'name': 'b'}],
                              'joints': [{'name': 'j', 'type': 'revolute', 'parent': 'a', 'child': 'b'}]}),
            ('machine_mesh', {'parts': [{'name': 'a'}, {'name': 'b'}],
                              'joints': [{'name': 'j', 'type': 'fixed', 'parent': 'a', 'child': 'b'},
                                         {'name': 'k', 'type': 'fixed', 'parent': 'b', 'child': 'a'}]}),
            ('machine_mesh', {'parts': [{'name': 'bad name'}]}),
            ('cloth3d', {'substeps': 1}), ('cloth3d', {'pin': 'none'}), ('cloth3d', {'cols': 31}),
            ('camera3d', {'up': [0, 0, 0]}), ('camera3d', {'near': 10, 'far': 1}),
            ('camera3d', {'position': [0, 0, 0], 'target': [0, 0, 0]}),
            ('camera3d', {'position': [0, 5, 0], 'target': [0, 0, 0], 'up': [0, 1, 0]}),
            ('skinning', {'vertices': [[0, 0, 0], [1, 0, 0], [0, 1, 0]]}),
            ('skinning', {'vertices': [[0, 0, 0], [1, 0, 0], [0, 1, 0]], 'faces': [[0, 1, 2]],
                          'weights': [[1], [1], [1]]}),
            ('uv_atlas', {'mesh': {'vertices': [[0, 0, 0]], 'faces': []}}),
            ('uv_atlas', {'mesh': {'vertices': [[0, 0, 0], [1, 0, 0], [0, 1, 0]], 'faces': [[0, 1, 5]]}}),
            ('uv_atlas', {'padding': 0.5}), ('uv_atlas', {'projection': 'sphere'}),
            ('area_lighting', {'hdri_summary': 'sky.hdr'}),
            ('area_lighting', {'hdri_summary': {'license': '', 'buckets': [
                {'direction': [0, 1, 0], 'radiance': [1, 1, 1]}]}}),
            ('area_lighting', {'samples': 64}),
            ('area_lighting', {'lights': [{'center': [0, 1, 0], 'u': [1, 0, 0], 'v': [2, 0, 0],
                                           'radiance': [1, 1, 1]}]}),
            ('export_mesh', {'nodes': [{'name': 'a'}]}),
            ('export_mesh', {'nodes': [{'name': 'a', 'parent': 'b'}, {'name': 'b'}],
                             'meshes': {'m': {'vertices': [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                                              'faces': [[0, 1, 2]]}}}),
            ('export_mesh', {'nodes': [{'name': 'a', 'mesh': 'missing'}],
                             'meshes': {'m': {'vertices': [[0, 0, 0], [1, 0, 0], [0, 1, 0]],
                                              'faces': [[0, 1, 2]]}}}),
            ('lod_budget', {'ratios': [0.5, 0.5]}), ('lod_budget', {'ratios': [0.0]}),
            ('lod_budget', {'distances': []}),
            ('cutaway', {'plane_normal': [0, 0, 0]}),
            ('cutaway', {'parts': [{'name': 'a', 'cut': 'yes'}]}),
        ]
        for op, params in bad:
            with self.subTest(op=op, params=params):
                with self.assertRaises(ValueError):
                    M.run(op, params)

    def test_vertex_cap(self):
        verts = [[float(i), 0.0, 0.0] for i in range(M.MAX_VERTICES + 1)]
        with self.assertRaises(ValueError):
            M.run('uv_atlas', {'mesh': {'vertices': verts, 'faces': [[0, 1, 2]]}})

    def test_direct_call_unknown_kw(self):
        for fn in M.OPS.values():
            with self.assertRaises(ValueError):
                fn(bogus=1)

    def test_module_is_pure(self):
        tree = ast.parse(Path(M.__file__).read_text(encoding='utf-8'))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported |= {a.name.split('.')[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split('.')[0])
            elif isinstance(node, ast.Call):
                self.assertNotIn(getattr(node.func, 'id', None),
                                 ('open', 'exec', 'eval', 'compile', 'print', '__import__'))
        self.assertFalse(imported & FORBIDDEN_IMPORTS)
        self.assertLessEqual(imported, ALLOWED_IMPORTS)


class TestMachineMesh(unittest.TestCase):  # 18.01
    def test_touching_passes_overlap_reported(self):
        parts = [{'name': 'a', 'shape': 'box', 'size': [1, 1, 1], 'position': [0, 0, 0]},
                 {'name': 'b', 'shape': 'box', 'size': [1, 1, 1], 'position': [1, 0, 0]},
                 {'name': 'c', 'shape': 'box', 'size': [1, 1, 1], 'position': [0.5, 0.8, 0]}]
        r = M.run('machine_mesh', {'parts': parts})['result']
        status = {(p['a'], p['b']): p['status'] for p in r['pairs']}
        self.assertEqual(status[('a', 'b')], 'touching')
        self.assertEqual(status[('a', 'c')], 'interfering')
        self.assertEqual(status[('b', 'c')], 'interfering')
        self.assertFalse(r['interference_free'])
        self.assertEqual({(p['a'], p['b']) for p in r['interferences']}, {('a', 'c'), ('b', 'c')})

    def test_rotated_boxes_sat_separates_where_aabb_overlaps(self):
        # 45-degree box: its AABB reaches x = 0.707 but the box itself stays clear of b.
        parts = [{'name': 'a', 'size': [1, 1, 1], 'rotation_deg': [0, 0, 45]},
                 {'name': 'b', 'size': [1, 1, 1], 'position': [1.15, 1.15, 0]}]
        r = M.run('machine_mesh', {'parts': parts})['result']
        self.assertEqual(r['pairs'][0]['method'], 'sat_obb')
        self.assertEqual(r['pairs'][0]['status'], 'clear')

    def test_default_machine(self):
        r = M.run('machine_mesh')['result']
        status = {(p['a'], p['b']): p for p in r['pairs']}
        self.assertEqual(status[('base', 'column')]['status'], 'touching')
        self.assertEqual(status[('shaft', 'gear')]['status'], 'interfering')
        self.assertTrue(status[('shaft', 'gear')]['joint_pair'])
        self.assertEqual(r['roots'], ['base'])
        self.assertEqual(r['degrees_of_freedom'], 1)
        base = r['parts'][0]
        self.assertAlmostEqual(base['volume'], 0.6 * 0.1 * 0.4, places=12)
        cyl = M.run('machine_mesh', {'parts': [{'name': 'c', 'shape': 'cylinder', 'radius': 1,
                                                 'height': 1, 'segments': 256}]})['result']
        self.assertAlmostEqual(cyl['parts'][0]['volume'], math.pi, delta=0.01)


class TestCarRig(unittest.TestCase):  # 18.02
    def test_turning_radius_and_ackermann(self):
        r = M.run('car_rig', {'wheelbase': 2.5, 'track': 1.5, 'steering_deg': 25})['result']
        R = 2.5 / math.tan(math.radians(25))
        self.assertAlmostEqual(r['turning_radius_rear_axle'], R, places=12)
        inner, outer = r['ackermann']['front_inner_deg'], r['ackermann']['front_outer_deg']
        self.assertGreater(inner, outer)
        self.assertGreater(inner, 25)
        self.assertLess(outer, 25)
        self.assertAlmostEqual(math.tan(math.radians(inner)), 2.5 / (R - 0.75), places=12)
        self.assertAlmostEqual(math.tan(math.radians(outer)), 2.5 / (R + 0.75), places=12)

    def test_wheel_rotation_per_distance(self):
        r = M.run('car_rig', {'steering_deg': 0, 'distance': 2 * math.pi * 0.33})['result']
        self.assertIsNone(r['turning_radius_rear_axle'])
        for w in r['wheels'].values():
            self.assertAlmostEqual(w['revolutions'], 1.0, places=12)
        r = M.run('car_rig', {'steering_deg': 20})['result']
        w = r['wheels']
        self.assertGreater(w['front_outer']['distance'], w['rear_outer']['distance'])
        self.assertGreater(w['rear_outer']['distance'], w['rear_inner']['distance'])

    def test_right_turn_mirrors(self):
        left = M.run('car_rig', {'steering_deg': 15})['result']
        right = M.run('car_rig', {'steering_deg': -15})['result']
        self.assertAlmostEqual(left['poses'][-1]['y'], -right['poses'][-1]['y'], places=12)
        self.assertAlmostEqual(left['ackermann']['front_inner_deg'],
                               -right['ackermann']['front_inner_deg'], places=12)


class TestCloth3d(unittest.TestCase):  # 18.03
    def test_default_run_stable(self):
        out = M.run('cloth3d')
        r = out['result']
        self.assertTrue(r['finite'])
        self.assertLessEqual(r['max_stretch_ratio'], 1.15)
        self.assertTrue(r['pinned_fixed'])
        self.assertTrue(r['energy_bounded'])
        self.assertTrue(r['stable'])
        self.assertLess(r['dt_ratio'], 0.9)
        for i in r['pinned_indices']:
            self.assertEqual(r['positions'][i][1], 0.0)
        self.assertEqual(r['positions'][r['pinned_indices'][1]][0], 0.9)
        # the free bottom row has sagged under gravity
        self.assertLess(r['positions'][-1][1], -0.9 + 1e-9)
        self.assertEqual(r['springs']['bend'], 2 * 10 * 8)

    def test_horizontal_drape_and_unstable_dt_rejected(self):
        r = M.run('cloth3d', {'start': 'horizontal', 'cols': 6, 'rows': 6, 'frames': 20})['result']
        self.assertTrue(r['finite'] and r['pinned_fixed'])
        with self.assertRaises(ValueError):
            M.run('cloth3d', {'k_struct': 1e5})


class TestCamera3d(unittest.TestCase):  # 18.04
    def test_fov_and_clipping(self):
        r = M.run('camera3d', {'position': [0, 0, 0], 'target': [0, 0, -10], 'near': 0.5, 'far': 50,
                               'points': [[0, 0, -5], [0, 0, -0.2], [0, 0, 3], [0, 0, -80],
                                          [100, 0, -5]]})['result']
        self.assertAlmostEqual(r['hfov_deg'], 39.6, delta=0.05)
        reasons = [p['reason'] for p in r['points']]
        self.assertEqual(reasons, ['visible', 'clipped_near', 'behind_camera', 'clipped_far',
                                   'outside_frustum'])
        self.assertTrue(r['points'][0]['visible'])
        self.assertAlmostEqual(r['points'][0]['pixel'][0], 960, places=6)
        self.assertAlmostEqual(r['points'][0]['ndc'][2], (50 + 0.5) / (50 - 0.5) - 2 * 50 * 0.5 / (49.5 * 5),
                               places=9)

    def test_depth_of_field(self):
        r = M.run('camera3d', {'focus_distance': 3.0})['result']['depth_of_field']
        H = (50 ** 2 / (2.8 * 0.03) + 50) / 1000
        self.assertAlmostEqual(r['hyperfocal_m'], H, places=12)
        self.assertLess(r['near_limit_m'], 3.0)
        self.assertGreater(r['far_limit_m'], 3.0)
        far = M.run('camera3d', {'focus_distance': 100.0})['result']['depth_of_field']
        self.assertIsNone(far['far_limit_m'])


class TestSkinning(unittest.TestCase):  # 18.05
    def test_rest_pose_unchanged_and_bend_distortion(self):
        r = M.run('skinning')['result']
        self.assertLess(r['rest_max_displacement'], 1e-12)
        self.assertGreater(r['max_skin_distortion'], 0.0)
        self.assertTrue(math.isfinite(r['max_skin_distortion']))
        # tip vertex fully bound to the lower bone: (2,-0.1,-0.1) -> rotate 90 deg about z at x=1
        tip = r['posed_vertices'][-4]
        self.assertAlmostEqual(tip[0], 1.1, places=12)
        self.assertAlmostEqual(tip[1], 1.0, places=12)
        self.assertAlmostEqual(tip[2], -0.1, places=12)

    def test_weights_normalised_and_rejected(self):
        verts = [[0, 0, 0], [1, 0, 0], [2, 0, 0], [1, 1, 0]]
        faces = [[0, 1, 3], [1, 2, 3]]
        bones = [{'name': 'a', 'head': [0, 0, 0]}, {'name': 'b', 'parent': 0, 'head': [1, 0, 0]}]
        w = [[1.0005, 0.0], [0.5, 0.5004], [0.0, 1.0], [0.3, 0.7]]
        r = M.run('skinning', {'vertices': verts, 'faces': faces, 'weights': w, 'bones': bones})['result']
        self.assertGreater(r['input_weight_sum_max_error'], 1e-4)
        self.assertLess(r['normalised_weight_sum_max_error'], 1e-12)
        self.assertLess(r['rest_max_displacement'], 1e-12)
        self.assertEqual(r['max_skin_distortion'], 0.0)
        with self.assertRaises(ValueError):
            M.run('skinning', {'vertices': verts, 'faces': faces, 'bones': bones,
                               'weights': [[0.6, 0.6], [0.5, 0.5], [0, 1], [0.3, 0.7]]})
        with self.assertRaises(ValueError):
            M.run('skinning', {'vertices': verts, 'faces': faces, 'bones': bones,
                               'weights': [[-0.1, 1.1], [0.5, 0.5], [0, 1], [0.3, 0.7]]})


class TestUvAtlas(unittest.TestCase):  # 18.06
    def test_box_packing(self):
        r = M.run('uv_atlas', {'padding': 0.03, 'include_uvs': True})['result']
        self.assertEqual(r['island_count'], 6)
        self.assertEqual(r['seam_count'], 12)
        self.assertTrue(r['within_unit_square'])
        self.assertEqual(r['island_rect_overlaps'], 0)
        self.assertEqual(r['overlapping_face_pairs_within_islands'], 0)
        self.assertTrue(r['padding_respected'])
        self.assertGreaterEqual(r['min_gap_between_islands'], 0.03 - 1e-9)
        self.assertGreaterEqual(r['min_border'], 0.03 - 1e-9)
        for tri in r['face_uvs']:
            for u, v in tri:
                self.assertTrue(0 <= u <= 1 and 0 <= v <= 1)
        rects = [i['rect'] for i in r['islands']]
        for i in range(len(rects)):
            for k in range(i + 1, len(rects)):
                a, b = rects[i], rects[k]
                self.assertTrue(a[2] + 0.03 - 1e-9 <= b[0] or b[2] + 0.03 - 1e-9 <= a[0]
                                or a[3] + 0.03 - 1e-9 <= b[1] or b[3] + 0.03 - 1e-9 <= a[1])

    def test_planar_projection_detects_folds(self):
        r = M.run('uv_atlas', {'projection': 'planar', 'planar_axis': 'z'})['result']
        self.assertEqual(r['island_count'], 1)
        self.assertEqual(r['seam_count'], 0)
        self.assertGreater(r['overlapping_face_pairs_within_islands'], 0)


class TestAreaLighting(unittest.TestCase):  # 18.07
    def test_occluded_point_darker(self):
        r = M.run('area_lighting')['result']
        pts = {p['name']: p for p in r['points']}
        self.assertLess(pts['under_occluder']['luminance'], pts['open_floor']['luminance'])
        self.assertEqual(pts['under_occluder']['region'], 'shadowed')
        self.assertEqual(pts['open_floor']['region'], 'lit')
        self.assertEqual(r['environment']['license'], 'CC0 example summary (synthetic)')

    def test_irradiance_scales_with_area(self):
        def run(half):
            return M.run('area_lighting', {
                'lights': [{'center': [0, 10, 0], 'u': [half, 0, 0], 'v': [0, 0, 0.1],
                            'radiance': [5, 5, 5]}],
                'occluders': [], 'use_default_hdri': False,
                'points': [{'position': [0, 0, 0], 'normal': [0, 1, 0]}]})['result']['points'][0]
        e1, e2 = run(0.1)['luminance'], run(0.2)['luminance']
        self.assertAlmostEqual(e2 / e1, 2.0, delta=0.01)
        # small distant light ~ L * A / d^2
        self.assertAlmostEqual(e1, 5 * 0.04 / 100, delta=1e-4)


class TestExportMesh(unittest.TestCase):  # 18.08
    def test_roundtrip_and_gltf_asset(self):
        r = M.run('export_mesh')['result']
        rt = r['roundtrip']
        self.assertTrue(rt['ok'])
        self.assertEqual(rt['obj_object_count'], rt['expected_object_count'])
        self.assertEqual(rt['gltf_object_count'], rt['expected_object_count'])
        self.assertEqual(rt['obj_vertex_count'], rt['expected_vertex_count'])
        self.assertEqual(rt['gltf_vertex_count'], rt['expected_vertex_count'])
        g = json.loads(r['gltf_json'])
        self.assertEqual(g['asset']['version'], '2.0')
        self.assertEqual(g, r['gltf'])
        self.assertEqual(len(g['meshes']), 3)  # gear mesh shared by two nodes
        uri = g['buffers'][0]['uri']
        data = base64.b64decode(uri.split(',', 1)[1])
        self.assertEqual(len(data), g['buffers'][0]['byteLength'])
        acc = g['accessors'][0]
        first = struct.unpack_from('<3f', data, 0)
        for k in range(3):
            self.assertGreaterEqual(first[k], acc['min'][k])
            self.assertLessEqual(first[k], acc['max'][k])
        self.assertIn('o gear_b', r['obj_text'])
        self.assertIn('newmtl brass', r['mtl_text'])

    def test_custom_scene(self):
        tri = {'vertices': [[0, 0, 0], [1, 0, 0], [0, 1, 0]], 'faces': [[0, 1, 2]]}
        r = M.run('export_mesh', {'nodes': [{'name': 'root', 'mesh': 't'},
                                            {'name': 'child', 'parent': 'root', 'mesh': 't',
                                             'translation': [1, 2, 3], 'scale': [2, 2, 2]}],
                                  'meshes': {'t': tri}, 'include_text': False})['result']
        self.assertTrue(r['roundtrip']['ok'])
        self.assertEqual(r['roundtrip']['expected_vertex_count'], 6)
        self.assertNotIn('obj_text', r)


class TestLodBudget(unittest.TestCase):  # 18.09
    def test_monotonic_decimation_and_budget(self):
        r = M.run('lod_budget')['result']
        lods = r['lods']
        self.assertEqual(lods[0]['vertices'], r['source_vertices'])
        self.assertEqual(lods[0]['max_error'], 0.0)
        for a, b in zip(lods, lods[1:]):
            self.assertLess(b['vertices'], a['vertices'])
            self.assertGreater(b['max_error'], a['max_error'])
            self.assertLessEqual(b['vertices'], max(3, round(b['ratio'] * r['source_vertices'])))
        self.assertTrue(r['vertex_count_monotonic'] and r['error_monotonic'])
        self.assertTrue(r['budget_met'])
        self.assertLessEqual(r['total_ms'], r['budget_ms'])
        self.assertAlmostEqual(r['total_ms'], sum(i['cost_ms'] for i in r['instances']), places=12)

    def test_tight_and_loose_budgets(self):
        loose = M.run('lod_budget', {'budget_ms': 100.0})['result']
        self.assertEqual(loose['degrade_steps'], 0)
        tight = M.run('lod_budget', {'budget_ms': 0.0001})['result']
        self.assertFalse(tight['budget_met'])
        self.assertTrue(all(i['lod'] in (None, len(tight['lods']) - 1) for i in tight['instances']))


class TestCutaway(unittest.TestCase):  # 18.10
    def test_cut_and_explode(self):
        r = M.run('cutaway', {'include_meshes': True})['result']
        self.assertTrue(r['all_cut_parts_clean'])
        self.assertTrue(r['assembled_overlapping_pairs'])
        self.assertTrue(r['exploded_parts_separated'])
        self.assertEqual(r['exploded_overlapping_pairs'], [])
        for p in r['parts']:
            self.assertLessEqual(p['max_signed_distance'], 1e-9)
            self.assertGreater(p['section_crossing_faces'], 0)
            off = p['explode_offset']
            for v in p['mesh']['vertices']:
                self.assertLessEqual(v[2] - off[2], 1e-9)  # plane z = 0, z > 0 removed
        boxes = [p['exploded_aabb'] for p in r['parts']]
        for i in range(len(boxes)):
            for k in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[k]
                gap = max(max(b['min'][j] - a['max'][j], a['min'][j] - b['max'][j]) for j in range(3))
                self.assertGreater(gap, 0)

    def test_fixed_small_explode_reports_overlap(self):
        r = M.run('cutaway', {'explode_distance': 0.0})['result']
        self.assertFalse(r['exploded_parts_separated'])
        whole = M.run('cutaway', {'plane_point': [0, 0, 5]})['result']
        self.assertEqual([p['vertices'] for p in whole['parts']],
                         [p['source_vertices'] for p in whole['parts']])
        gone = M.run('cutaway', {'plane_point': [0, 0, -5]})['result']
        self.assertEqual(len(gone['fully_removed_parts']), 3)


if __name__ == '__main__':
    unittest.main()
