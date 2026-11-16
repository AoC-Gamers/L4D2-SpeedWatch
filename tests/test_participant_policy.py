"""Checks limited participant-policy logic, not SourcePawn or SRCDS execution.

The selected functions use a C-compatible subset of SourcePawn. They are extracted
from production source, with only the `public` modifier removed, and compiled with
C++ test doubles for SourceMod. This does not validate the SourcePawn compiler,
engine callbacks, properties, plugin integration, timing or performance.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'addons/sourcemod/scripting/l4d2_speedwatch/observation.sp'
def product_source():
    directory = SOURCE.parent
    return '\n'.join(p.read_text() for p in sorted(directory.glob('*.sp')))



def function(source: str, name: str) -> str:
    match = re.search(r'^(?:public )?(?:bool|void|int|any|NativeObservationState) ' + re.escape(name) + r'\([^\n]*\)\n\{', source, re.M)
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
#include <cstdlib>
constexpr int MAXPLAYERS = 64;
int MaxClients = MAXPLAYERS;
bool g_bHuman[65]{}, g_bMonitor[65]{}, g_bHasSample[65]{};
int g_Strikes[65]{};
float g_Debt[65]{};
struct Episode { bool active = false; } g_Detections[65];
bool inGame[65]{}, alive[65]{};
int teams[65]{};
struct Runtime {
    bool mapLoaded = true, observationEnded = false, modeNeedsSync = false;
    bool paused = false, pauseNeedsSync = false, inReady = false, readyUpNeedsSync = false;
} g_Runtime;
bool nativeReady = true;
bool bNativeDetectorReady() { return nativeReady; }
bool IsClientInGame(int c) { assert(c > 0 && c <= MaxClients); return inGame[c]; }
bool IsPlayerAlive(int c) { assert(inGame[c]); return alive[c]; }
int GetClientTeam(int c) { assert(inGame[c]); return teams[c]; }
void SetClient(int c, int team, bool human = true, bool living = true) {
    g_bHuman[c] = human; inGame[c] = true; alive[c] = living; teams[c] = team;
}
'''

MAIN = r'''
int main() {
    for (int n : {0, 1, 2, 4, 6, 8, 12}) {
        for (int c = 1; c <= MaxClients; ++c) SetClient(c, 1);
        for (int c = 21; c < 21 + n; ++c) SetClient(c, c % 2 == 0 ? 2 : 3);
        int count = 0;
        for (int c = 1; c <= MaxClients; ++c) count += bIsPlayingHuman(c);
        assert(count == n);
    }
    assert(!bIsPlayingHuman(-1) && !bIsPlayingHuman(0) && !bIsPlayingHuman(65));
    for (int team : {2, 3}) { SetClient(64, team); assert(bIsPlayingHuman(64)); }
    for (int team : {0, 1, 4, 5}) { SetClient(64, team); assert(!bIsPlayingHuman(64)); }
    SetClient(64, 2, false); assert(!bIsPlayingHuman(64));
    SetClient(64, 2, true, false); assert(!bIsPlayingHuman(64));
    SetClient(64, 2); inGame[64] = false; assert(!bIsPlayingHuman(64));
    const int c = 30;
    assert(!bHasClientObservation(c));
    g_bMonitor[c] = true; assert(bHasClientObservation(c)); g_bMonitor[c] = false;
    g_bHasSample[c] = true; assert(bHasClientObservation(c)); g_bHasSample[c] = false;
    g_Detections[c].active = true; assert(bHasClientObservation(c)); g_Detections[c].active = false;
    g_Strikes[c] = 2; assert(bHasClientObservation(c)); g_Strikes[c] = 0;
    g_Debt[c] = 2; assert(bHasClientObservation(c)); g_Debt[c] = 0;
    assert(bCanObserve());
    nativeReady = false; assert(!bCanObserve()); nativeReady = true;
    g_Runtime.mapLoaded = false; assert(!bCanObserve()); g_Runtime.mapLoaded = true;
    for (bool* flag : {&g_Runtime.observationEnded, &g_Runtime.modeNeedsSync,
         &g_Runtime.paused, &g_Runtime.pauseNeedsSync, &g_Runtime.inReady,
         &g_Runtime.readyUpNeedsSync}) {
        *flag = true; assert(!bCanObserve()); *flag = false;
    }
    assert(bCanObserve());
}
'''


class ParticipantLogicTests(unittest.TestCase):
    def test_native_readiness_lifecycle_population_and_eligibility(self):
        compiler = shutil.which('c++')
        if compiler is None:
            self.skipTest('C++ compiler absent; this is not a SourcePawn compiler test')
        source = product_source()
        functions = '\n'.join(function(source, name) for name in
            ('bCanObserve', 'bIsPlayingHuman', 'bHasClientObservation'))
        with tempfile.TemporaryDirectory() as tmp:
            unit = Path(tmp) / 'policy.cpp'
            unit.write_text('#include <initializer_list>\n' + PRELUDE + functions + MAIN)
            binary = Path(tmp) / 'policy'
            subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                '-O0', str(unit), '-o', str(binary)], check=True, timeout=30)
            subprocess.run([str(binary)], check=True, timeout=5)


class ParticipantSourceTests(unittest.TestCase):
    def test_timer_and_api_use_same_policy(self):
        source = product_source()
        self.assertIn('if (!bIsPlayingHuman(client))', source)
        self.assertIn('&& g_bMonitor[client] && bIsPlayingHuman(client);', source)
        self.assertIn('if (bHasClientObservation(client))\n            {\n'
                      '                ResetClient(client, now, SpeedWatchReason_ClientUnavailable);', source)


if __name__ == '__main__':
    unittest.main()
