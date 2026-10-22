"""Small offline regressions. All writes use TemporaryDirectory or memory SQLite."""

import io
import json
import sqlite3
import sys
import tempfile
import unittest
import urllib.request
from concurrent.futures import CancelledError, Future
from contextlib import closing
from datetime import datetime
from email.message import Message
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.response import addinfourl

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "addon"))

import config
import droid_sync
import droid_timing
import droid_models
import factory_quota
import renderer
import run_state
import service
import settings_guard

SCHEMA = (Path(__file__).parent / "schema.sql").read_text(encoding="utf-8")


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.sessions = self.root / "sessions"
        self.sessions.mkdir()
        self.db = self.root / "usage.db"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.executescript(SCHEMA)
            conn.execute("INSERT INTO model_pricing VALUES ('model-a','Model A','1','2','0.1','1')")
        self.now = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0).timestamp()

    def write_session(self, sid="s1", counts=(10, 20, 0, 0), models=("model-a",)):
        (self.sessions / (sid + ".settings.json")).write_text(json.dumps({
            "tokenUsage": dict(zip(droid_sync.FIELDS, counts)), "model": models[-1],
        }), encoding="utf-8")
        (self.sessions / (sid + ".jsonl")).write_text("\n".join(json.dumps({
            "type": "message", "message": {"role": "assistant", "modelId": model},
        }) for model in models), encoding="utf-8")

    def sync(self, at=None, **kwargs):
        with patch("droid_sync.time.time", return_value=self.now if at is None else at):
            return droid_sync.sync(self.sessions, self.db, **kwargs)

    def rows(self, query):
        with closing(sqlite3.connect(self.db)) as conn:
            return conn.execute(query).fetchall()

    def test_repeated_sync_and_same_day_delta(self):
        self.write_session()
        self.assertEqual(self.sync().inserted, 1)
        self.assertEqual(self.sync(self.now + 10).inserted, 0)
        self.write_session(counts=(15, 30, 0, 0))
        self.assertEqual(self.sync(self.now + 20).inserted, 1)
        self.assertEqual(self.rows("SELECT SUM(input_tokens),SUM(output_tokens) FROM proxy_request_logs"), [(15, 30)])
        today = droid_sync.today_usage(self.db)
        self.assertEqual((today["tokens"], today["unallocatedTokens"]), (15, 30))
        self.assertEqual(today["cost"], 0.000025)

    def test_bad_session_does_not_rollback_good_session(self):
        self.write_session("good")
        self.write_session("huge", (2**63, 1, 0, 0))
        result = self.sync()
        self.assertEqual(result.inserted, 1)
        self.assertTrue(any("huge" in warning for warning in result.warnings))
        self.assertEqual(self.rows("SELECT session_id FROM proxy_request_logs"), [("good",)])

    def test_incomplete_duplicate_is_excluded(self):
        self.write_session()
        other = self.sessions / "other"
        other.mkdir()
        (other / "s1.settings.json").write_text('{"tokenUsage":', encoding="utf-8")
        self.assertEqual(self.sync().inserted, 0)

    def test_counter_rollback_preserves_accounting(self):
        self.write_session()
        self.sync()
        self.write_session(counts=(5, 10, 0, 0))
        result = self.sync(self.now + 10)
        self.assertEqual(result.inserted, 0)
        self.assertTrue(result.warnings)
        self.assertEqual(self.rows("SELECT totals_json FROM droid_addon_snapshots"), [("[10, 20, 0, 0]",)])

    def test_cancellation_rolls_back_records_and_checkpoints(self):
        self.write_session()
        cancelled = [False]
        insert = droid_sync._insert
        def cancel_after_insert(*args, **kwargs):
            insert(*args, **kwargs)
            cancelled[0] = True
        with patch("droid_sync._insert", side_effect=cancel_after_insert):
            with self.assertRaises(CancelledError):
                self.sync(cancelled=lambda: cancelled[0])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM proxy_request_logs"), [(0,)])
        self.assertEqual(self.rows("SELECT name FROM sqlite_master WHERE name='droid_addon_snapshots'"), [])

    def test_mixed_models_and_extreme_prices_remain_unknown(self):
        self.write_session("mixed", models=("model-a", "model-b"))
        self.write_session("expensive")
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE model_pricing SET input_cost_per_million='1e9999'")
        self.assertEqual(self.sync().inserted, 2)
        self.assertEqual(self.rows("SELECT SUM(cost_known) FROM droid_addon_records"), [(0,)])

    def test_invalid_snapshot_and_cross_day_import_are_unallocated(self):
        self.write_session()
        self.sync()
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE droid_addon_snapshots SET observed_at=1e30")
        self.write_session(counts=(11, 21, 0, 0))
        self.assertEqual(self.sync(self.now + 10).inserted, 1)
        self.write_session(counts=(12, 22, 0, 0))
        self.assertEqual(self.sync(self.now + 86400).inserted, 1)
        self.assertEqual(self.rows("SELECT DISTINCT time_quality FROM droid_addon_records"), [("unallocated",)])

    def test_missing_database_is_not_created(self):
        missing = self.root / "missing.db"
        self.assertTrue(droid_sync.sync(self.sessions, missing).warnings)
        self.assertFalse(missing.exists())

    def test_corrupt_historical_session_does_not_block_other_imports(self):
        self.write_session("corrupt")
        self.sync()
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE proxy_request_logs SET input_tokens='invalid'")
        self.write_session("good")
        result = self.sync(self.now + 10)
        self.assertEqual(result.inserted, 1)
        self.assertTrue(any("corrupt" in warning for warning in result.warnings))

    def test_nonfinite_historical_cost_is_not_sent_to_renderer(self):
        self.write_session(counts=(0, 0, 0, 0))
        self.sync()
        self.write_session()
        self.sync(self.now + 10)
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE proxy_request_logs SET total_cost_usd='1e9999'")
        today = droid_sync.today_usage(self.db)
        self.assertIsNone(today["cost"])
        self.assertTrue(today["costError"])
        json.dumps(today, allow_nan=False)

    def unknown_observed(self):
        self.write_session(counts=(0, 0, 0, 0))
        self.sync()
        self.write_session(counts=(401, 9, 0, 0))
        (self.sessions / "s1.jsonl").write_text(
            json.dumps({"type": "message", "message": {"role": "user"}}), encoding="utf-8",
        )
        self.sync(self.now + 10)
        return droid_models.ModelRequest("s1", "title-1", "model-title", self.now + 1,
                                         self.now + 2, "session-title-generation")

    def test_runtime_model_repairs_existing_unknown_without_new_tokens(self):
        request = self.unknown_observed()
        accounting = "SELECT request_id,input_tokens,output_tokens,total_cost_usd,created_at,latency_ms FROM proxy_request_logs"
        before = self.rows(accounting)
        result = self.sync(self.now + 20, model_requests=[request])
        self.assertEqual((result.inserted, result.models_updated), (0, 1))
        self.assertEqual(self.rows(accounting), before)
        self.assertEqual(self.rows("SELECT request_model,model FROM proxy_request_logs"),
                         [("model-title", "model-title [模型推定] [费用未知]")])
        self.assertEqual(self.rows("SELECT model_quality,cost_known FROM droid_addon_records"), [("inferred", 0)])
        self.assertEqual(self.sync(self.now + 30, model_requests=[request]).models_updated, 0)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM droid_hook_models"), [(1,)])

    def test_multiple_requests_do_not_guess_a_model(self):
        request = self.unknown_observed()
        other = droid_models.ModelRequest("s1", "other", "model-other", self.now + 3,
                                          self.now + 4, "")
        self.assertEqual(self.sync(self.now + 20, model_requests=[request, other]).models_updated, 0)
        self.assertEqual(self.rows("SELECT request_model FROM proxy_request_logs"), [(droid_models.UNKNOWN,)])

    def test_auxiliary_request_prevents_charging_all_tokens_to_transcript_model(self):
        self.write_session(counts=(0, 0, 0, 0))
        self.sync()
        self.write_session()
        title = droid_models.ModelRequest("s1", "title", "model-title", self.now + 1, self.now + 2, "session-title-generation")
        main = droid_models.ModelRequest("s1", "main", "model-a", self.now + 3, self.now + 4, "")
        self.sync(self.now + 10, model_requests=[title, main])
        self.assertEqual(self.rows("SELECT request_model FROM proxy_request_logs"), [("Droid 混合模型",)])
        self.assertEqual(self.rows("SELECT model_quality,cost_known FROM droid_addon_records"), [("mixed", 0)])

    def test_overlapping_rows_cannot_reuse_model_evidence(self):
        request = self.unknown_observed()
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("""INSERT INTO proxy_request_logs
                (request_id,provider_id,app_type,model,request_model,session_id,latency_ms,status_code,created_at,data_source)
                VALUES ('overlap','_droid_session','droid','model-a','model-a','s1',0,200,?,'droid_session')""", (int(self.now),))
            conn.execute("INSERT INTO droid_addon_records VALUES ('overlap','observed','single',0,'',?,?)",
                         (self.now, self.now + 10))
        self.assertEqual(self.sync(self.now + 20, model_requests=[request]).models_updated, 0)

    def test_unbounded_or_outside_sample_models_stay_unknown(self):
        request = self.unknown_observed()
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("UPDATE droid_addon_records SET sample_start=NULL,time_quality='legacy'")
        self.assertEqual(self.sync(self.now + 20, model_requests=[request]).models_updated, 0)

    def test_current_configuration_does_not_override_transcript_model(self):
        self.write_session()
        path = self.sessions / "s1.settings.json"
        settings = json.loads(path.read_text())
        settings["model"] = "model-chosen-later"
        path.write_text(json.dumps(settings), encoding="utf-8")
        self.sync()
        self.assertEqual(self.rows("SELECT request_model FROM proxy_request_logs"), [("model-a",)])

    def test_cancelled_model_repair_rolls_back_label_and_evidence(self):
        request = self.unknown_observed()
        cancelled = [False]
        repair = droid_models.repair
        def cancel_after_repair(*args):
            count = repair(*args)
            cancelled[0] = True
            return count
        with patch("droid_models.repair", side_effect=cancel_after_repair):
            with self.assertRaises(CancelledError):
                self.sync(self.now + 20, model_requests=[request], cancelled=lambda: cancelled[0])
        self.assertEqual(self.rows("SELECT request_model FROM proxy_request_logs"), [(droid_models.UNKNOWN,)])
        self.assertEqual(self.rows("SELECT COUNT(*) FROM droid_hook_models"), [(0,)])


class ModelLogTests(unittest.TestCase):
    def test_auxiliary_model_uses_request_field_not_parent_tag_and_rejects_retries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "droid-log-single.log"
            events = []
            for offset, retried in [(0, False), (10, True)]:
                for delta, metric, fields in [
                    (2, droid_timing.DURATION, {"value": 1.2, "messageCallType": "session-title-generation"}),
                    (3, droid_timing.SUCCESS, {"value": 1, "assistantMessageId": str(offset), "retried": retried}),
                ]:
                    event = {"modelId": "model-title", "metric": metric, "factory.process.instance_id": "process",
                             "tags": {"sessionId": "s1", "traceId": "trace", "spanId": "span", "modelId": "model-parent"}, **fields}
                    events.append(f"[2026-10-21T15:08:{offset + delta:02d}.000Z] INFO: [{metric}] | Context: " + json.dumps(event))
            path.write_text("\n".join(events) + "\n", encoding="utf-8")
            reader = droid_models.ModelReader()
            requests, warnings = reader.read(Path(directory))
            self.assertFalse(warnings)
            self.assertEqual([(r.model, r.call_type) for r in requests], [("model-title", "session-title-generation")])
            # Conflicting copies of the same request across rotations are not evidence.
            path.with_name(path.name + ".1").write_text(
                path.read_text().replace('"model-title"', '"conflicting-model"'), encoding="utf-8",
            )
            self.assertEqual(reader.read(Path(directory))[0], [])


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(":memory:")
        self.addCleanup(self.conn.close)
        self.conn.executescript(SCHEMA)
        droid_sync._ensure_schema(self.conn)

    def row(self, rid="r1", start=10, end=100, quality="single", latency=0):
        self.conn.execute("""INSERT INTO proxy_request_logs
            (request_id,provider_id,app_type,model,request_model,session_id,
             input_tokens,output_tokens,latency_ms,status_code,created_at,data_source)
            VALUES (?,'_droid_session','droid','model-a','model-a','s1',10,20,?,200,100,'droid_session')""",
            (rid, latency))
        self.conn.execute("INSERT INTO droid_addon_records VALUES (?,'observed',?,1,'',?,?)",
                          (rid, quality, start, end))

    @staticmethod
    def request(mid="m1", ended=30):
        return droid_timing.RequestTiming("s1", mid, "model-a", (10, 20, 0, 0), ended, 10000, 1000)

    def enrich(self, requests):
        return droid_timing.enrich(self.conn, requests, record_table=droid_sync.RECORD_TABLE)[0]

    def test_unique_request_matches_once_and_preserves_existing_timing(self):
        self.row()
        self.assertEqual(self.enrich([self.request()]), 1)
        self.assertEqual(self.enrich([self.request()]), 0)
        self.assertEqual(self.conn.execute("SELECT latency_ms,first_token_ms,duration_ms FROM proxy_request_logs").fetchone(), (10000, 1000, 9000))

    def test_missing_boundary_unknown_model_and_existing_timing_are_skipped(self):
        self.row("history", start=None)
        self.row("unknown", quality="unknown")
        self.row("existing", latency=4000)
        self.row("damaged", start="invalid")
        self.assertEqual(self.enrich([self.request()]), 0)

    def test_ambiguous_row_also_reserves_candidate_evidence(self):
        self.row("broad", start=10, end=100)
        self.row("narrow", start=10, end=40)
        self.assertEqual(self.enrich([self.request(), self.request("m2", 60)]), 0)


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = self.root / "device-settings.json"
        cfg = dict(config.DEFAULTS, ccSwitchDbPath=str(self.root / "custom" / "usage.db"),
                   droidSessionsDir=str(self.root / "sessions"), droidLogsDir=str(self.root / "logs"))
        self.addCleanup(patch.stopall)
        patch("config.native_settings_path", return_value=self.settings).start()
        patch("factory_quota.resolve_api_key", return_value="").start()
        self.worker = patch("service.ThreadPoolExecutor").start().return_value
        self.worker.submit.side_effect = lambda *args: Future()
        self.svc = service.DataService(cfg, Mock(), lambda: True)
        self.addCleanup(self.svc.close)

    def settings_value(self, enabled, interval=5000):
        self.settings.write_text(json.dumps({"sessionAutoSyncEnabled": enabled,
                                           "usageDashboardRefreshIntervalMs": interval}), encoding="utf-8")
        self.svc.next_settings = 0

    def test_disabled_auto_sync_still_accepts_manual_sync(self):
        self.settings_value(False)
        self.svc.tick()
        self.worker.submit.assert_not_called()
        self.svc.request(sync=True)
        self.svc.tick()
        self.worker.submit.assert_called_once()

    def test_device_settings_apply_to_custom_db_and_live_toggle(self):
        self.settings_value(False)
        self.svc.tick()
        self.settings_value(True, 10000)
        self.svc.tick()
        self.assertEqual(self.svc.scan_interval, 10)
        self.worker.submit.assert_called_once()
        self.svc.tick()
        self.worker.submit.assert_called_once()  # Slow jobs never overlap.

    def test_bad_settings_pause_scanning_without_stopping_service(self):
        self.settings.write_text("{", encoding="utf-8")
        self.svc.tick()
        self.worker.submit.assert_not_called()
        self.assertTrue(self.svc.payload()["syncWarnings"])
        self.settings_value(True, float("inf"))
        self.svc.tick()
        self.assertEqual(self.svc.scan_interval, 60)

    def test_committed_changes_publish_revision_and_old_date_is_hidden(self):
        self.settings_value(True)
        self.svc.tick()
        self.svc.sync_job.set_result((droid_sync.SyncResult(inserted=1), {
            "available": True, "date": "2001-01-01", "tokens": 50,
        }))
        self.svc.tick()
        payload = self.svc.payload()
        self.assertEqual(payload["usageRevision"], 1)
        self.assertFalse(payload["today"]["available"])

    def test_quota_failure_keeps_success_time_and_data(self):
        self.svc.quota = {"updatedAt": 123, "windows": [{"usedPercent": 40}]}
        self.svc.last_key = self.svc.quota_key = "fake"
        self.svc.quota_job = Future()
        self.svc.quota_job.set_exception(factory_quota.QuotaError("offline"))
        self.svc._collect()
        self.assertEqual(self.svc.quota["updatedAt"], 123)
        self.assertEqual(self.svc.quota["windows"], [{"usedPercent": 40}])
        self.assertTrue(self.svc.quota["stale"])

    def test_model_only_repair_publishes_usage_revision(self):
        self.settings_value(True)
        self.svc.tick()
        self.svc.sync_job.set_result((droid_sync.SyncResult(models_updated=1), {}))
        self.svc.tick()
        self.assertEqual(self.svc.payload()["usageRevision"], 1)
        self.svc.state.log.assert_called_with("usage_models_updated", records=1)

    def test_failed_summary_does_not_discard_committed_import_result(self):
        db = config.db_path(self.svc.cfg)
        db.parent.mkdir()
        db.touch()
        with patch.object(self.svc.timing_reader, "read", return_value=([], [])), \
                patch("droid_sync.sync", return_value=droid_sync.SyncResult(inserted=1)), \
                patch("droid_sync.today_usage", side_effect=sqlite3.OperationalError("overflow")):
            result, today = self.svc._sync(self.svc.cfg)
        self.assertEqual(result.inserted, 1)
        self.assertFalse(today["available"])


class QuotaTests(unittest.TestCase):
    def test_redirect_is_blocked_before_a_second_request(self):
        requests = []
        class FakeHTTP(urllib.request.HTTPHandler):
            def http_open(self, req):
                requests.append(req.full_url)
                headers = Message()
                headers["Location"] = "http://other.invalid/stolen"
                response = addinfourl(io.BytesIO(b""), headers, req.full_url, 302)
                response.msg = "Found"
                return response
        build = urllib.request.build_opener
        with patch("factory_quota.urllib.request.build_opener", side_effect=lambda *h: build(
                urllib.request.ProxyHandler({}), FakeHTTP(), *h)):
            with self.assertRaisesRegex(factory_quota.QuotaError, "重定向"):
                factory_quota._get("http://factory.invalid", "/limits", "test-key")
        self.assertEqual(requests, ["http://factory.invalid/limits"])

    def test_all_key_sources_validate_without_echoing_secret(self):
        key = "private-key\r\ninjected-header"
        with patch.dict("os.environ", {"FACTORY_API_KEY": key}):
            with self.assertRaises(factory_quota.QuotaError) as error:
                factory_quota.resolve_api_key("")
        self.assertNotIn("private-key", str(error.exception))

    def test_unreadable_credential_file_is_not_reported_as_missing_key(self):
        with patch.dict("os.environ", {"FACTORY_API_KEY": ""}), patch("pathlib.Path.read_text", side_effect=PermissionError()):
            with self.assertRaises(PermissionError):
                factory_quota.resolve_api_key("")


class RendererTests(unittest.TestCase):
    def test_click_survives_transport_failure_and_is_not_repeated(self):
        page = renderer.PageHook({"webSocketDebuggerUrl": "ws://unused"}, 1)
        page.connection = Mock()
        page.registration_attempted = True
        info = {"version": renderer.VERSION, "instanceId": "a", "ready": True, "syncNow": 1, "refresh": 0}
        page.connection.evaluate.side_effect = [info, TimeoutError(), info, None, info]
        with self.assertRaises(TimeoutError):
            page.update("source", {})
        self.assertTrue(page.update("source", {})["syncNow"])
        self.assertFalse(page.update("source", {})["syncNow"])

    def test_wrong_hook_version_is_reinstalled(self):
        page = renderer.PageHook({"webSocketDebuggerUrl": "ws://unused"}, 1)
        page.connection = Mock()
        page.registration_attempted = True
        page.connection.evaluate.side_effect = [{"version": "old"}, None]
        self.assertEqual(page.update("new-source", {}), {})
        self.assertEqual(page.connection.evaluate.call_args.args, ("new-source",))

    def test_refresh_counter_does_not_force_perpetual_rerenders(self):
        page = renderer.PageHook({"webSocketDebuggerUrl": "ws://unused"}, 1)
        page.connection = Mock()
        page.registration_attempted = True
        info = {"version": renderer.VERSION, "instanceId": "a", "ready": True, "syncNow": 0, "refresh": 1}
        page.connection.evaluate.side_effect = [info, None, info]
        self.assertTrue(page.update("source", {})["refresh"])
        self.assertFalse(page.update("source", {})["refresh"])
        self.assertEqual(page.connection.evaluate.call_count, 3)


class SettingsGuardTests(unittest.TestCase):
    def test_invalid_settings_are_backed_up_without_overwriting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            original = root / "settings.json"
            content = b'{"setting": 1, "setting": 2}'
            original.write_bytes(content)
            with patch("config.native_settings_path", return_value=original):
                with self.assertRaises(RuntimeError):
                    settings_guard.preserve_before_launch(root / "backups")
            self.assertEqual(original.read_bytes(), content)
            self.assertEqual(next((root / "backups").iterdir()).read_bytes(), content)

    def test_status_write_retries_short_windows_sharing_violation(self):
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "status.json"
            original_replace = run_state.os.replace
            attempts = []
            def replace(source, target):
                attempts.append(source)
                if len(attempts) < 3:
                    raise PermissionError("fixture sharing violation")
                original_replace(source, target)
            with patch("run_state.os.replace", side_effect=replace), patch("run_state.time.sleep"):
                run_state.RunState._write(destination, {"state": "attached"})
            self.assertEqual(json.loads(destination.read_text()), {"state": "attached"})
            self.assertEqual(len(attempts), 3)
            self.assertEqual(list(Path(temp).glob("*.tmp")), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
