"""Exercise production SP window policy/cadence/episodes with C++ doubles.

Float bit-casts and array syntax are adapted mechanically. These tests do not
execute the SP VM or certify SDK hooks, network behaviour or gameplay thresholds.
"""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_participant_policy import function, product_source
import re

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'addons/sourcemod/scripting'

PRELUDE = r'''
#include <cassert>
#include <cstring>
#include <cmath>
#include <limits>
#include <vector>
#include <string>
#include <cstdio>
constexpr int SPEEDWATCH_CORE_API_VERSION = 2, SPEEDWATCH_CORE_SAMPLE_CELLS = 48;
enum NativeObservationState { NativeObservation_Absent=0, NativeObservation_Published, NativeObservation_Stale, NativeObservation_Interrupted, NativeObservation_MissingCapability, NativeObservation_Invalid, NativeObservation_First, NativeObservation_Duplicate };
NativeObservationState g_CoreStates[65]{};
constexpr int NATIVE_DETECTOR_CAPS = 7;
constexpr float PERSISTENCE_SECONDS = 30;
struct Runtime { bool coreAvailable = true, coreControllerAvailable=true, coreNeedsSync = false, sampleValid=true; int coreCapabilities = 7, observationGeneration=3; } g_Runtime;
bool g_CoreWindowReady[65]{}, g_CoreHasSample[65]{}, g_bHasSample[65]{}, g_bMonitor[65]{};
int g_CoreSamples[65][48]{}, g_Strikes[65]{};
float g_NextAlert[65]{},g_LastEngineTime=0,g_LastInterval=0;int g_LastTick=0,MaxClients=64;
constexpr int DEBUG_LIFECYCLE=2;
void DebugLog(int,const char*,const char*,...){}
void PulseNativeCore(bool enabled){assert(!enabled);}
float GetTickInterval(){return 1.f/30;}int GetGameTickCount(){return 900;}

float g_Debt[65]{}, g_LastRate[65]{}, g_LastRatio[65]{}, g_GraceUntil[65]{};
struct Sample { int accountId = 42, userId = 100; float commandsPerSecond=0,ratio=0; } g_ClientSamples[65];
struct Episode { bool active = false; int accountId = 0, userId = 0; float recoveryTime = 0, persistenceTime = 0; int persistenceMarker = 0; } g_Detections[65];
enum SpeedWatchDetectionState { SpeedWatchDetection_Active, SpeedWatchDetection_Recovered, SpeedWatchDetection_Interrupted };
enum SpeedWatchDetectionReason { SpeedWatchReason_None, SpeedWatchReason_NormalCadence, SpeedWatchReason_InvalidSample, SpeedWatchReason_ObservationReset };
struct Cvar { float FloatValue; } grace{5}, recovery{3};
Cvar *g_cvGrace = &grace, *g_cvRecoveryTime = &recovery;
struct Event { SpeedWatchDetectionState state; SpeedWatchDetectionReason reason; int userid; };
std::vector<Event> events;
void QueueDetectionEvent(int c, SpeedWatchDetectionState s, SpeedWatchDetectionReason r) { events.push_back({s,r,g_Detections[c].userId}); }
struct Persistence { int userid, accountid, marker; float seconds; };
std::vector<Persistence> markers;
void QueueDetectionPersistence(int c) { markers.push_back({g_Detections[c].userId,g_Detections[c].accountId,++g_Detections[c].persistenceMarker,g_Detections[c].persistenceTime}); }
void SetNativeParticipant(int c, bool enabled) { if (!enabled) { g_CoreWindowReady[c] = false; g_CoreHasSample[c] = false; } }
void strcopy(char* dst, int length, const char* src) { std::snprintf(dst,length,"%s",src); }
void StrCat(char* dst, int length, const char* src) { std::strncat(dst,src,length-std::strlen(dst)-1); }
struct NativeCadenceWindow {int commands=0;float duration=0,interval=0;};
struct Log {bool bDebug(int){return false;}} g_Log;
constexpr int DEBUG_SAMPLES=4;
int currentWire[48]{};bool sampleAvailable=true;
bool SpeedWatchCore_GetSample(int,int* out,int length){assert(length==48);std::memcpy(out,currentWire,sizeof(currentWire));return sampleAvailable;}
int GetClientUserId(int){return 100;}int GetClientSerial(int){return 200;}int GetClientTeam(int){return 2;}
void LogNativeWindow(int,const int*,bool,int){}
float BitsFloat(int bits) { float f; std::memcpy(&f,&bits,4); return f; }
int FloatBits(float f) { int bits; std::memcpy(&bits,&f,4); return bits; }
'''
MAIN = r'''
int main() {
    const int c = 21;
    int s[48]{};
    s[0]=2; s[47]=1; s[1]=48; s[2]=1; s[3]=7; s[5]=100; s[6]=200;
    s[8]=3; s[9]=1; s[10]=1; s[12]=1000000; s[14]=2000000;
    s[18]=FloatBits(1.f/30); s[19]=FloatBits(1); s[20]=2; s[33]=30;
    auto accept = [&]() { return bAcceptNativeWindow(c,s,100,200,2,3); };
    auto advance = [&]() { ++s[10]; s[12]=s[14]; s[14]+=1000000; };
    auto reasons = [&]() { return NativeWindowRejectReasons(c,s,100,200,2,3); };
    char names[320];
    assert(reasons()==WINDOW_FIRST);
    FormatWindowReasons(0,names,sizeof(names)); assert(std::string(names)=="none");
    FormatWindowReasons(WINDOW_IGNORED|WINDOW_PAUSED,names,sizeof(names));
    assert(std::string(names)=="ignored_blocks|paused_blocks");
    FormatWindowReasons(WINDOW_UNAVAILABLE,names,sizeof(names)); assert(std::string(names)=="sample_unavailable");
    FormatWindowReasons(WINDOW_CORE_NOT_READY,names,sizeof(names)); assert(std::string(names)=="core_not_ready");
    // Partial first window never creates a usable public sample.
    s[4]=32; assert(!accept()); s[4]=0;
    advance(); assert(accept());
    assert(reasons() & WINDOW_DUPLICATE);
    assert(!accept()); // duplicate must not charge debt/recovery twice
    advance(); assert(accept());
    advance(); advance(); assert(reasons()==WINDOW_GAP); assert(!accept()); // missed window
    advance(); assert(accept());
    ++s[9]; advance(); assert(reasons()==WINDOW_GENERATION); assert(!accept()); // participant generation
    advance(); assert(accept());
    ++s[45]; advance(); assert(reasons()==WINDOW_INSTANCE); assert(!accept());
    advance(); assert(accept());
    // Identity, epoch, team, header, source, capability and signed count checks.
    for (int index : {0,1,2,3,5,6,8,20,34}) {
        int old=s[index]; s[index]=(index==3 ? 1 : 999); advance();
        const int expected = index<=2 ? WINDOW_HEADER : index==3 ? WINDOW_CAPABILITIES
            : index==5 || index==6 ? WINDOW_IDENTITY : index==8 ? WINDOW_EPOCH
            : index==20 ? WINDOW_TEAM : WINDOW_COUNTER;
        assert(reasons()==expected); assert(!accept()); s[index]=old;
        advance(); assert(!accept()); advance(); assert(accept());
    }
    // NaN and out-of-bounds durations/intervals cannot enter arithmetic.
    for (int index : {18,19}) {
        int old=s[index];
        for (float value : {0.f,-1.f,3.f,std::numeric_limits<float>::quiet_NaN(),std::numeric_limits<float>::infinity()}) {
            s[index]=FloatBits(value); advance(); assert(reasons() & WINDOW_TIMING); assert(!accept());
        }
        s[index]=old; advance(); assert(!accept()); advance(); assert(accept());
    }
    s[33]=-1; advance(); assert(!accept()); s[33]=30;
    advance(); assert(!accept()); advance(); assert(accept());
    // Quality, ignored and paused blocks invalidate; loss metadata alone does not.
    for (int quality : {1,2,4,8,16,32}) {
        s[4]=quality; advance(); assert(reasons()==WINDOW_QUALITY); assert(!accept()); s[4]=0; advance(); assert(accept());
    }
    for (int index : {27,28}) {
        s[index]=1; advance(); assert(reasons()==0); assert(accept()); s[index]=0;
    }
    for (int index : {29,30,31,32}) {
        s[index]=1; advance(); assert(reasons()==(index<31 ? WINDOW_IGNORED : WINDOW_PAUSED)); assert(!accept()); s[index]=0; advance(); assert(accept());
    }
    // Sample ID high bits can roll over; timestamps, not signed ordering, link windows.
    s[10]=-1; s[11]=1; advance(); assert(accept()); s[10]=0; ++s[11]; advance(); assert(accept());
    assert(bNativeDetectorReady());
    g_Runtime.coreAvailable=false; assert(!bNativeDetectorReady()); g_Runtime.coreAvailable=true;
    g_Runtime.coreNeedsSync=true; assert(!bNativeDetectorReady()); g_Runtime.coreNeedsSync=false;
    for (int caps : {0,1,2,3,5,6}) { g_Runtime.coreCapabilities=caps; assert(!bNativeDetectorReady()); }
    g_Runtime.coreCapabilities=7;
    // Feed only accepted native evidence through the real cadence and episode code.
    for (int i=0;i<30;++i) { EvaluateNativeCadence(c,30,33,60,3); UpdateDetectionEpisode(c,30,33,1,3); }
    assert(g_Debt[c]==0 && events.empty());
    for (int i=0;i<20;++i) { EvaluateNativeCadence(c,45,33,60,3); UpdateDetectionEpisode(c,45,33,1,3); }
    assert(g_Debt[c]==120 && g_Strikes[c]==3 && events.size()==1);
    assert(events[0].state==SpeedWatchDetection_Active && events[0].userid==100);
    UpdateDetectionEpisode(c,0,33,1,3); assert(g_Detections[c].recoveryTime==0);
    UpdateDetectionEpisode(c,30,33,1,3); assert(g_Detections[c].recoveryTime==1);
    // Invalid native evidence interrupts, rather than reporting a recovery.
    g_bMonitor[c]=true; g_bHasSample[c]=true;
    ClearClientDetection(c,10,SpeedWatchReason_InvalidSample);
    assert(!g_bHasSample[c] && g_bMonitor[c] && g_CoreWindowReady[c]);
    assert(g_Debt[c]==0 && g_Strikes[c]==0 && g_GraceUntil[c]==15);
    assert(events.size()==2 && events[1].state==SpeedWatchDetection_Interrupted);
    assert(events[1].reason==SpeedWatchReason_InvalidSample);
    // A new episode recovers only after consecutive valid nonzero normal cadence.
    g_Strikes[c]=3; UpdateDetectionEpisode(c,45,33,1,3);
    UpdateDetectionEpisode(c,30,33,1,3); UpdateDetectionEpisode(c,30,33,1,3);
    assert(g_Detections[c].active); UpdateDetectionEpisode(c,30,33,1,3);
    assert(!g_Detections[c].active && events.back().state==SpeedWatchDetection_Recovered);
    ResetClient(c,20); assert(!g_bMonitor[c] && !g_CoreWindowReady[c]);
}
'''


LOSS_REGRESSIONS = r'''
int main() {
    const int c=21, required=3;
    int s[48]{};
    s[0]=2; s[47]=1; s[1]=48; s[2]=1; s[3]=7; s[5]=100; s[6]=200;
    s[8]=3; s[9]=1; s[10]=1; s[12]=1000000; s[14]=2000000;
    s[18]=FloatBits(1.f/30); s[19]=FloatBits(1); s[20]=2;
    assert(!bAcceptNativeWindow(c,s,100,200,2,3)); // prime first window
    auto reset = [&]() {
        ClearClientDetection(c,0,SpeedWatchReason_ObservationReset);
        events.clear();
    };
    auto feed = [&](int commands,int dropped) {
        ++s[10]; s[12]=s[14]; s[14]+=1000000; s[33]=commands; s[27]=dropped;
        // Even very large loss metadata must not reset grace or discard evidence.
        assert(NativeWindowRejectReasons(c,s,100,200,2,3)==0);
        assert(bAcceptNativeWindow(c,s,100,200,2,3));
        const float duration=BitsFloat(s[19]), interval=BitsFloat(s[18]);
        const float allowed=duration/interval*1.10f, buffer=2.f/interval;
        EvaluateNativeCadence(c,commands,allowed,buffer,required);
        UpdateDetectionEpisode(c,commands,allowed,duration,required);
        assert(g_GraceUntil[c]==5); // no new grace caused by loss metadata
    };
    reset();
    for (int i=0;i<60;++i) feed(30,813);
    assert(events.empty() && g_Debt[c]==0 && g_Strikes[c]==0);
    // Lost-time catch-up: several idle windows, then one extreme burst.
    reset();
    for (int i=0;i<5;++i) feed(0,1);
    feed(444,813);
    assert(g_Strikes[c]==1 && !g_Detections[c].active);
    for (int i=0;i<60;++i) feed(30,1);
    assert(events.empty() && g_Debt[c]==0 && g_Strikes[c]==0);
    // Two large consecutive bursts remain below the existing three-window rule.
    reset(); feed(444,813); feed(444,813);
    assert(g_Strikes[c]==2 && events.empty());
    feed(30,813);
    assert(g_Strikes[c]==0 && events.empty());
    // Isolated bursts never build a consecutive streak, even with residual debt.
    reset();
    for (int i=0;i<20;++i) { feed(444,813); feed(30,1); }
    assert(events.empty() && !g_Detections[c].active);
    // Observed comp-dev attempt counts: sustained excess now opens an episode.
    reset();
    const int attempts[]={337,133,227,444,416,267,335};
    const int drops[]={175,79,470,813,787,440,720};
    for (int i=0;i<7;++i) {
        feed(attempts[i],drops[i]);
        if (i<2) assert(events.empty());
        else assert(events.size()==1 && g_Detections[c].active && g_Strikes[c]==required);
    }
    assert(events[0].state==SpeedWatchDetection_Active && events[0].userid==100);
    assert(std::fabs(g_Debt[c]-120.f)<0.01f);
}
'''


PERSISTENCE_REGRESSIONS = r'''
int main() {
 const int c=21;
 g_Strikes[c]=3;
 UpdateDetectionEpisode(c,500,33,1,3);
 assert(events.size()==1&&markers.empty()&&g_Detections[c].persistenceTime==0);
 for(int i=0;i<29;i++) UpdateDetectionEpisode(c,500,33,1,3);
 assert(markers.empty());
 UpdateDetectionEpisode(c,500,33,1,3);
 assert(markers.size()==1&&markers[0].marker==1&&markers[0].seconds==30);
 for(int i=0;i<30;i++) UpdateDetectionEpisode(c,500,33,1,3);
 assert(markers.size()==2&&markers[1].marker==2&&events.size()==1);
 for(const auto& marker:markers) assert(marker.userid==100&&marker.accountid==42);
 // Fractional native durations: never round wall-clock time into confirmed excess.
 for(int i=0;i<59;i++) UpdateDetectionEpisode(c,500,33,0.5f,3);
 assert(markers.size()==2);UpdateDetectionEpisode(c,500,33,0.5f,3);assert(markers.size()==3);
 // One normal/empty/unconfirmed window breaks the interval without closing early.
 for(int mode=0;mode<3;mode++){
  for(int i=0;i<29;i++) UpdateDetectionEpisode(c,500,33,1,3);
  if(mode==2)g_Strikes[c]=1;
  UpdateDetectionEpisode(c,mode==0?30:mode==1?0:500,33,1,3);
  g_Strikes[c]=3;
  assert(g_Detections[c].active&&g_Detections[c].persistenceTime==0);
  auto prior=markers.size();
  for(int i=0;i<29;i++) UpdateDetectionEpisode(c,500,33,1,3);
  assert(markers.size()==prior);UpdateDetectionEpisode(c,500,33,1,3);assert(markers.size()==prior+1);
 }
 for(int i=0;i<29;i++) UpdateDetectionEpisode(c,500,33,1,3);
 ClearClientDetection(c,100,SpeedWatchReason_InvalidSample);
 assert(!g_Detections[c].active&&g_Detections[c].persistenceTime==0&&g_Detections[c].persistenceMarker==0);
 auto count=markers.size();g_Strikes[c]=3;g_ClientSamples[c].userId=101;
 UpdateDetectionEpisode(c,500,33,1,3);
 for(int i=0;i<29;i++) UpdateDetectionEpisode(c,500,33,1,3);
 assert(markers.size()==count);UpdateDetectionEpisode(c,500,33,1,3);
 assert(markers.back().userid==101&&markers.back().marker==1);
 for(int i=0;i<3;i++) UpdateDetectionEpisode(c,30,33,1,3);
 assert(!g_Detections[c].active&&events.back().state==SpeedWatchDetection_Recovered);
}
'''


class NativeDetectorTests(unittest.TestCase):
    def run_production_policy(self, main):
        compiler = shutil.which('c++')
        if not compiler:
            self.skipTest('C++ compiler absent')
        native = (SCRIPTS / 'l4d2_speedwatch/native_client.sp').read_text()
        detector = product_source()
        functions = '\n'.join(function(native, n) for n in ('eNativeObservationState','bNativeDetectorReady','NativeWindowRejectReasons','bAcceptNativeWindow','FormatWindowReasons','ReadNativeObservation','EvaluateNativeWindow'))
        defines = '\n'.join(re.findall(r'^#define WINDOW_.*$', native, re.M))
        constants = '\n'.join(line for line in (SCRIPTS/'include/l4d2_speedwatch_core.inc').read_text().splitlines() if line.startswith('#define CoreCell_') or line.startswith('#define SPEEDWATCH_WINDOW_') or line.startswith('#define SPEEDWATCH_QUALITY_'))
        functions = constants + '\n' + defines + '\n' + functions
        functions += '\n' + '\n'.join(function(detector, n) for n in
            ('EvaluateNativeCadence','EndDetectionEpisode','UpdateDetectionEpisode','ClearClientDetection','ResetClient','ResetAll'))
        functions = functions.replace('int[] sample','int* sample').replace('NativeCadenceWindow window','NativeCadenceWindow& window')
        functions = functions.replace('const char[] reason','const char* reason')
        functions = functions.replace('char[] text', 'char text[]').replace('const int* sample', 'const int sample[]').replace('view_as<float>', 'BitsFloat').replace('view_as<int>', 'static_cast<int>')
        functions = functions.replace('g_cvGrace.FloatValue','g_cvGrace->FloatValue').replace('g_cvRecoveryTime.FloatValue','g_cvRecoveryTime->FloatValue')
        functions = functions.replace('float(commands)','static_cast<float>(commands)')
        with tempfile.TemporaryDirectory() as tmp:
            unit=Path(tmp)/'native_detector.cpp'; binary=Path(tmp)/'native_detector'
            unit.write_text(PRELUDE+functions+main)
            subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-O0',str(unit),'-o',str(binary)],check=True,timeout=30)
            subprocess.run([str(binary)],check=True,timeout=5)

    def test_production_window_cadence_and_episode_policy(self):
        self.run_production_policy(MAIN)

    def test_loss_metadata_bursts_and_sustained_excess(self):
        self.run_production_policy(LOSS_REGRESSIONS)

    def test_persistence_uses_consecutive_confirmed_native_durations(self):
        self.run_production_policy(PERSISTENCE_REGRESSIONS)

    def test_absent_stale_partial_and_duplicate_windows_never_evaluate(self):
        self.run_production_policy(r"""
int main(){const int c=21;NativeCadenceWindow w;
sampleAvailable=false;currentWire[47]=2;
assert(!EvaluateNativeWindow(c,w)&&g_CoreStates[c]==NativeObservation_Stale);
currentWire[47]=0;assert(!EvaluateNativeWindow(c,w)&&g_CoreStates[c]==NativeObservation_Absent);
sampleAvailable=true;currentWire[0]=2;currentWire[1]=48;currentWire[2]=1;currentWire[3]=7;currentWire[47]=1;
currentWire[5]=100;currentWire[6]=200;currentWire[8]=3;currentWire[9]=1;currentWire[10]=1;
currentWire[12]=1000000;currentWire[14]=2000000;currentWire[18]=FloatBits(1.f/30);currentWire[19]=FloatBits(1);currentWire[20]=2;currentWire[33]=444;
assert(!EvaluateNativeWindow(c,w)&&g_CoreStates[c]==NativeObservation_First);
++currentWire[10];currentWire[12]=currentWire[14];currentWire[14]+=1000000;
assert(EvaluateNativeWindow(c,w)&&w.commands==444&&w.duration==1);
assert(!EvaluateNativeWindow(c,w)&&g_CoreStates[c]!=NativeObservation_Published);
++currentWire[10];currentWire[12]=currentWire[14];currentWire[14]+=1000000;currentWire[4]=32;currentWire[47]=3;
assert(!EvaluateNativeWindow(c,w)&&g_CoreStates[c]==NativeObservation_Interrupted);
}
""")

    def test_global_reset_interrupts_all_slots_and_preserves_cooldown(self):
        self.run_production_policy(r"""
int main(){for(int c : {1,21,64}){g_Strikes[c]=3;g_NextAlert[c]=123;g_bMonitor[c]=true;UpdateDetectionEpisode(c,500,33,1,3);}
ResetAll(20,"configuration");assert(!g_Runtime.sampleValid&&g_Runtime.observationGeneration==4);
assert(events.size()==6);for(int c : {1,21,64}) assert(!g_Detections[c].active&&!g_bMonitor[c]&&g_GraceUntil[c]==25&&g_NextAlert[c]==123);
for(int i=3;i<6;i++)assert(events[i].state==SpeedWatchDetection_Interrupted);
}
""")

    def test_timer_has_one_source_and_status_does_not_consume_windows(self):
        detector = product_source()
        native = (SCRIPTS / 'l4d2_speedwatch/native_client.sp').read_text()
        self.assertNotIn('OnPlayerRunCmdPre',detector)
        self.assertNotIn('g_Commands',detector)
        self.assertIn('EvaluateNativeWindow(client, window)',detector)
        self.assertIn('UpdateDetectionEpisode(client, commands, allowed, duration, required)',detector)
        self.assertNotIn('ReadNativeWindow(',function(native,'ShowNativeCoreStatus'))
        self.assertNotIn('SpeedWatchCore_GetSample(',function(native,'ShowNativeCoreStatus'))
