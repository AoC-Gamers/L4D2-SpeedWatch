"""Source-contract checks and small models, not SRCDS runtime tests."""
import ast
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULES = ROOT / "addons/sourcemod/scripting/l4d2_speedwatch"
DETECTOR = (MODULES / "detector.sp").read_text(encoding="utf-8")
CONTEXT = (MODULES / "context.sp").read_text(encoding="utf-8")


def body(source, name):
    match = re.search(r"\b(?:bool|int|void|float|Action|any)\s+" + re.escape(name)
                      + r"\([^\n]*\)\s*\{", source)
    if not match:
        raise AssertionError(f"Missing function: {name}")
    start = match.end()
    depth = 1
    for pos in range(start, len(source)):
        depth += (source[pos] == "{") - (source[pos] == "}")
        if depth == 0:
            return source[start:pos]
    raise AssertionError(f"Unclosed function: {name}")


def playing_team(team):
    # Execute the actual, intentionally simple team predicate from SourcePawn.
    expression = re.fullmatch(r"\s*return\s+(.+);\s*",
                              body(CONTEXT, "IsPlayingTeam")).group(1)
    tree = ast.parse(expression.replace("||", " or "), mode="eval")
    allowed = (ast.Expression, ast.BoolOp, ast.Or, ast.Compare, ast.Eq,
               ast.Name, ast.Load, ast.Constant)
    if any(not isinstance(node, allowed) for node in ast.walk(tree)):
        raise AssertionError("Team predicate needs an updated test adapter")
    return eval(compile(tree, "<IsPlayingTeam>", "eval"),
                {"__builtins__": {}}, {"team": team})


class ContextContractTests(unittest.TestCase):
    def test_context_module_is_in_release_manifest(self):
        manifest = json.loads((ROOT / "plugin-package-map.json").read_text())
        modules = manifest["artifact"]["addons"]["sourcemod"]["scripting"]["l4d2_speedwatch"]["files"]
        self.assertIn("context.sp", modules)
        self.assertIn('#include "context.sp"', DETECTOR)

    def test_status_excludes_spectators_without_assuming_eight_players(self):
        source = (MODULES.parent / "l4d2_speedwatch.sp").read_text()
        status = body(source, "OnStatusCommand")
        self.assertIn("IsPlayingTeam(GetClientTeam(target))", status)
        self.assertIn("target <= MaxClients", status)
        self.assertIn("CaptureMovementProfile(profile)", status)

    def test_only_playing_teams(self):
        self.assertEqual([t for t in range(-1, 8) if playing_team(t)], [2, 3])

    def test_variable_populations_and_high_slots(self):
        # Fixture selection model: no relation between client index and team size.
        for survivors, infected in ((0, 0), (1, 1), (2, 2), (3, 3), (4, 4), (1, 3), (5, 5)):
            with self.subTest(survivors=survivors, infected=infected):
                slots = [(19 + i, 2, True, True) for i in range(survivors)]
                slots += [(35 + i, 3, True, True) for i in range(infected)]
                slots += [(2, 1, True, True), (3, 2, False, True), (4, 3, True, False)]
                selected = [slot for slot, team, human, in_game in slots
                            if human and in_game and playing_team(team)]
                self.assertEqual(len(selected), survivors + infected)
                self.assertTrue(all(slot > 8 for slot in selected))

    def test_profile_uses_slots_not_match_size(self):
        profile = body(CONTEXT, "CaptureMovementProfile")
        self.assertIn("client <= MaxClients", profile)
        self.assertIn("!g_bHuman[client] || !IsClientInGame(client)", profile)
        self.assertNotIn("IsPlayerAlive", profile)
        self.assertNotRegex(DETECTOR, r"client\s*<=\s*8\b")
        self.assertNotRegex(DETECTOR, r"(?:survivorLimit|infectedLimit|survivors|infected)\s*[<>=]")

    def test_timer_and_api_share_team_predicate(self):
        self.assertIn("!IsPlayingTeam(GetClientTeam(client))", body(DETECTOR, "OnSampleTimer"))
        self.assertIn("IsPlayingTeam(GetClientTeam(client))", body(DETECTOR, "Native_GetClientSample"))

    def test_hot_path_skips_unmonitored_clients(self):
        hot = body(DETECTOR, "OnPlayerRunCmdPre")
        self.assertIn("!bCanObserve() || !g_bMonitor[client]", hot)
        self.assertLess(hot.index("return;"), hot.index("g_Commands[client]++"))
        for forbidden in ("GetEntProp", "HasEntProp", "CaptureMovement", "GetClientTeam", "new "):
            self.assertNotIn(forbidden, hot)

    def test_context_is_captured_before_external_callbacks(self):
        timer = body(DETECTOR, "OnSampleTimer")
        self.assertLess(timer.index("CaptureMovementContext(client, now, profile, context)"),
                        timer.index("UpdateDetectionEpisode(client"))
        self.assertIn("SendAlert(client, context, profile)", timer)
        writer = body(CONTEXT, "WriteMovementContext")
        self.assertNotIn("GetEntProp", writer)
        self.assertNotIn("GetClient", writer)

    def test_context_is_lazy_and_not_a_new_detection_signal(self):
        timer = body(DETECTOR, "OnSampleTimer")
        self.assertIn("g_Log.file != null && g_Strikes[client] >= required", timer)
        self.assertIn("if (!hasProfile)", timer)
        for forbidden in ("g_Debt", "g_Strikes", "g_NextAlert", "CreateTimer", "OnGameFrame",
                          "TeleportEntity", "SetEntProp", "KickClient", "BanClient"):
            self.assertNotIn(forbidden, CONTEXT)
        self.assertNotIn("[MAXPLAYERS", CONTEXT)

    def test_nominal_command_budget_is_unchanged(self):
        timer = body(DETECTOR, "OnSampleTimer")
        for expression in ("float expected       = elapsed / interval;",
                           "float allowed  = expected * g_cvRate.FloatValue;",
                           "float buffer   = g_cvBurst.FloatValue / interval;",
                           "g_Debt[client] += float(commands) - allowed;",
                           "g_Debt[client] >= buffer && float(commands) > allowed"):
            self.assertIn(expression, timer)

    def test_optional_properties_and_config_are_explicitly_unknown(self):
        self.assertIn("value == null ? -1", body(CONTEXT, "ContextConVarInt"))
        self.assertIn("HasEntProp", body(CONTEXT, "ContextSendInt"))
        self.assertIn(": -1", body(CONTEXT, "ContextSendInt"))
        self.assertIn("return -1.0", body(CONTEXT, "ContextFloat"))
        self.assertIn("ContextFinite", body(CONTEXT, "ContextFloat"))
        self.assertIn("complete ? 0 : -1", body(CONTEXT, "ContextPinState"))

    def test_bhop_policy_handles_tank_without_treating_witch_as_player(self):
        policy = body(CONTEXT, "ConfiguredBhopPolicy")
        self.assertIn("zombieClass >= 1 && zombieClass <= 6", policy)
        self.assertIn("zombieClass == 8", policy)
        self.assertIn("bit = 6", policy)
        self.assertIn("if (bit < 0)", policy)
        self.assertIn("profile.infectedBhopFlags & (1 << bit)", policy)

    def test_snapshot_is_not_advertised_as_window_speed(self):
        writer = body(CONTEXT, "WriteMovementContext")
        self.assertIn("scope=sample_end", writer)
        self.assertIn("health_buffer_raw=", writer)
        self.assertIn("maxspeed_prop=", writer)
        self.assertIn("bhop_config=", writer)
        self.assertNotIn("speed_ratio=", writer)

    def test_alert_context_does_not_depend_on_debug(self):
        self.assertIn("WriteMovementContext(context, profile, true)", body(DETECTOR, "SendAlert"))
        writer = body(CONTEXT, "WriteMovementContext")
        self.assertIn("(!alert && !g_Log.bDebug(DEBUG_SAMPLES))", writer)
        self.assertIn("g_Log.Flush()", writer)

    def test_spectators_can_still_receive_staff_alerts(self):
        alert = body(DETECTOR, "SendAlert")
        self.assertIn("CheckCommandAccess", alert)
        self.assertNotIn("IsPlayingTeam", alert)
        self.assertNotIn("GetClientTeam", alert)

    def test_queue_cursor_preserves_reentrant_fifo_contract(self):
        flush = body(DETECTOR, "FlushDetectionEvents")
        self.assertIn("while (nextEvent < g_DetectionEvents.Length)", flush)
        self.assertIn("GetArray(nextEvent++", flush)
        self.assertNotIn("g_DetectionEvents.Erase(0)", flush)
        self.assertLess(flush.index("Call_Finish()"), flush.index("g_DetectionEvents.Clear()"))
        # Reference model for append during dispatch; not a SourceMod runtime test.
        queue = ["Active-A", "Active-B"]
        delivered = []
        cursor = 0
        while cursor < len(queue):
            event = queue[cursor]
            cursor += 1
            delivered.append(event)
            if event == "Active-A":
                queue.append("Interrupted-A")
        queue.clear()
        self.assertEqual(delivered, ["Active-A", "Active-B", "Interrupted-A"])
        self.assertEqual(queue, [])


if __name__ == "__main__":
    unittest.main()
