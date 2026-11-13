"""Checks limited participant-policy logic, not SourcePawn or SRCDS execution.

The selected functions use a C-compatible subset of SourcePawn. They are extracted
from production source, with only the `public` modifier removed, and compiled with
C++ test doubles for SourceMod. This does not validate the SourcePawn compiler,
engine callbacks, properties, plugin integration, timing or performance.
"""
from pathlib import Path
import hashlib
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'addons/sourcemod/scripting/l4d2_speedwatch/detector.sp'


def function(source: str, name: str) -> str:
    match = re.search(r'^(?:public )?(?:bool|void) ' + re.escape(name) + r'\([^\n]*\)\n\{', source, re.M)
    if match is None:
        raise AssertionError(f'Function not found: {name}')
    opening = source.index('{', match.start())
    depth = 0
    # The selected functions currently have no braces in strings or comments.
    for end in range(opening, len(source)):
        depth += (source[end] == '{') - (source[end] == '}')
        if depth == 0:
            return source[match.start():end + 1]
    raise AssertionError(f'Unterminated function: {name}')


PRELUDE = r'''
#include <cassert>
#include <cstddef>
#include <cstdlib>
constexpr int MAXPLAYERS = 64;
constexpr int DEBUG_COMMANDS = 16;
int MaxClients = MAXPLAYERS;
bool g_bHuman[65]{}, g_bMonitor[65]{}, g_bHasSample[65]{};
int g_Commands[65]{}, g_Strikes[65]{};
float g_Debt[65]{};
struct Episode { bool active = false; } g_Detections[65];
bool inGame[65]{}, alive[65]{};
int teams[65]{};
int entityCalls = 0;
struct Runtime {
    bool mapLoaded = true, observationEnded = false, modeNeedsSync = false;
    bool paused = false, pauseNeedsSync = false, inReady = false, readyUpNeedsSync = false;
} g_Runtime;
struct Logger {
    bool enabled = false;
    int checks = 0, writes = 0;
    bool bDebug(int) { ++checks; return enabled; }
    void Write(const char*, const char*) { ++writes; }
} g_Log;
bool IsClientInGame(int c) { assert(c > 0 && c <= MaxClients); ++entityCalls; return inGame[c]; }
bool IsPlayerAlive(int c) { assert(inGame[c]); ++entityCalls; return alive[c]; }
int GetClientTeam(int c) { assert(inGame[c]); ++entityCalls; return teams[c]; }
int GetClientUserId(int c) { assert(inGame[c]); return c + 1000; }
void Format(char* out, std::size_t n, const char*, ...) { assert(n > 0); out[0] = 0; }
void SetClient(int c, int team, bool human = true, bool living = true) {
    g_bHuman[c] = human; inGame[c] = true; alive[c] = living; teams[c] = team;
}
'''

MAIN = r'''
void Command(int c) {
    float vec[3]{}; int mouse[2]{};
    OnPlayerRunCmdPre(c, 0, 0, vec, vec, 0, 0, 1, 1, 0, mouse);
}
int main(int argc, char** argv) {
    assert(argc == 2);
    const int test = std::atoi(argv[1]);
    if (test == 1) {
        // Empty, solo practice, 1v1, 2v2, 3v3, 4v4, and >8: never wait for a quorum.
        for (int n : {0, 1, 2, 4, 6, 8, 12}) {
            for (int c = 1; c <= MaxClients; ++c) {
                SetClient(c, 1); g_bMonitor[c] = false; g_Commands[c] = 0;
            }
            for (int c = 21; c < 21 + n; ++c) {
                SetClient(c, c % 2 == 0 ? 2 : 3); g_bMonitor[c] = true;
            }
            int count = 0;
            g_Log = {}; g_Log.enabled = true;
            for (int c = 1; c <= MaxClients; ++c) {
                count += bIsPlayingHuman(c);
                const int before = entityCalls;
                Command(c);
                assert(entityCalls == before); // No entity lookups on the command path.
                assert(g_Commands[c] == (g_bMonitor[c] ? 1 : 0));
            }
            assert(count == n && g_Log.checks == n && g_Log.writes == n);
        }
    } else if (test == 2) {
        assert(!bIsPlayingHuman(-1) && !bIsPlayingHuman(0) && !bIsPlayingHuman(65));
        SetClient(64, 2); assert(bIsPlayingHuman(64));
        SetClient(64, 3); assert(bIsPlayingHuman(64));
        for (int t : {0, 1, 4, 5}) { SetClient(64, t); assert(!bIsPlayingHuman(64)); }
        SetClient(64, 2, false); assert(!bIsPlayingHuman(64));
        SetClient(64, 2, true, false); assert(!bIsPlayingHuman(64));
        SetClient(64, 2); inGame[64] = false; assert(!bIsPlayingHuman(64));
    } else if (test == 3) {
        g_Log.enabled = true;
        SetClient(10, 1); Command(10);
        SetClient(11, 2, true, false); Command(11);
        SetClient(12, 2, false); Command(12);
        Command(-1); Command(0); Command(65);
        assert(g_Log.checks == 0 && g_Log.writes == 0);
        assert(g_Commands[10] == 0 && g_Commands[11] == 0 && g_Commands[12] == 0);
    } else if (test == 4) {
        const int c = 30;
        assert(!bHasClientObservation(c));
        g_bMonitor[c] = true; assert(bHasClientObservation(c)); g_bMonitor[c] = false;
        g_bHasSample[c] = true; assert(bHasClientObservation(c)); g_bHasSample[c] = false;
        g_Detections[c].active = true; assert(bHasClientObservation(c)); g_Detections[c].active = false;
        g_Commands[c] = 2; assert(bHasClientObservation(c)); g_Commands[c] = 0;
        g_Strikes[c] = 2; assert(bHasClientObservation(c)); g_Strikes[c] = 0;
        g_Debt[c] = 2; assert(bHasClientObservation(c)); g_Debt[c] = 0;
        assert(!bHasClientObservation(c));
    } else if (test == 5) {
        SetClient(40, 2); g_bMonitor[40] = true; g_Log.enabled = true;
        g_Runtime.mapLoaded = false; Command(40); g_Runtime.mapLoaded = true;
        for (bool* flag : {&g_Runtime.observationEnded, &g_Runtime.modeNeedsSync,
             &g_Runtime.paused, &g_Runtime.pauseNeedsSync, &g_Runtime.inReady,
             &g_Runtime.readyUpNeedsSync}) {
            *flag = true; Command(40); *flag = false;
        }
        assert(g_Commands[40] == 0 && g_Log.checks == 0);
        Command(40); assert(g_Commands[40] == 1 && g_Log.writes == 1);
    } else { return 2; }
}
'''


class ParticipantLogicTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = shutil.which('c++')
        if compiler is None:
            raise unittest.SkipTest('C++ compiler absent; this is not a SourcePawn compiler test')
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        source = SOURCE.read_text(encoding='utf-8')
        functions = '\n'.join(function(source, name).removeprefix('public ') for name in
            ('bCanObserve', 'bIsPlayingHuman', 'bHasClientObservation', 'OnPlayerRunCmdPre'))
        unit = Path(cls.tmp.name) / 'policy.cpp'
        unit.write_text('#include <initializer_list>\n' + PRELUDE + functions + MAIN, encoding='utf-8')
        cls.binary = Path(cls.tmp.name) / 'policy'
        subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
            '-Wno-unused-parameter', '-O0', str(unit), '-o', str(cls.binary)], check=True, timeout=30)

    def run_case(self, case: int):
        subprocess.run([str(self.binary), str(case)], check=True, timeout=5)

    def test_population_sizes_and_high_slots(self): self.run_case(1)
    def test_exact_eligibility_and_bounds(self): self.run_case(2)
    def test_non_monitored_clients_do_not_count_or_trace(self): self.run_case(3)
    def test_only_observation_state_needs_reset(self): self.run_case(4)
    def test_observation_gates_still_suspend_commands(self): self.run_case(5)


class ParticipantSourceTests(unittest.TestCase):
    def test_timer_and_api_use_same_policy(self):
        source = SOURCE.read_text(encoding='utf-8')
        self.assertIn('if (!bIsPlayingHuman(client))', source)
        self.assertIn('&& g_bMonitor[client] && bIsPlayingHuman(client);', source)
        self.assertIn('if (bHasClientObservation(client))\n            {\n'
                      '                ResetClient(client, now, SpeedWatchReason_ClientUnavailable);', source)

    def test_existing_lifecycle_and_alert_functions_unchanged(self):
        source = SOURCE.read_text(encoding='utf-8')
        expected = EXPECTED_UNCHANGED
        for name, digest in expected.items():
            with self.subTest(function=name):
                self.assertEqual(hashlib.sha256(function(source, name).encode()).hexdigest(), digest)


EXPECTED_UNCHANGED = {
    "ResetClient": "ed83f58cdc02e644b1f2245ae52775aa66d9072dc7bd065bc342e5bb32485295",
    "ResetAll": "fda917c1d7183de9ac197f2a342318366f8857efa9effd5c14c35ebab7e5b04d",
    "UpdateDetectionEpisode": "1a8cf35957030c5d32715bce644ff3babced46133b712b0b5207d38e8aabfb72",
    "EndDetectionEpisode": "cb9d5c420a832ba348a87f808cfb1e6cfdd4c52d0d35652c6f0eb3954c37e446",
    "QueueDetectionEvent": "c855cfa4cd6643dc33b90ce0815b38d408366b1d264d91daf5712a565a596833",
    "FlushDetectionEvents": "f52c7ac13c01b621045b964412bbb11aede30c1d27e4a426c8643122b03e800a",
    "SendAlert": "bdd9ad45739df5fa0cbc84d34e093695336b9df97628cc17a110d69d0368a218",
    "StoreClientSample": "b546eefba4e858a7814894e068cda63c62955128a225e80d86667d58cabf4dbe"
}

if __name__ == '__main__':
    unittest.main()
