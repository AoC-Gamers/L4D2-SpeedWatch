"""Execute production lifecycle/query/alert bodies with modeled SourceMod; no VM claims."""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from test_participant_policy import function, product_source

ROOT=Path(__file__).resolve().parents[1]


def run_cpp(unit):
    compiler=shutil.which('c++')
    if not compiler:
        raise unittest.SkipTest('C++ compiler absent')
    with tempfile.TemporaryDirectory() as tmp:
        source=Path(tmp)/'contract.cpp';binary=Path(tmp)/'contract'
        source.write_text(unit)
        subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(source),'-o',str(binary)],check=True,timeout=30)
        subprocess.run([str(binary)],check=True,timeout=5)


class ObservationContractTests(unittest.TestCase):
    def test_dependencies_capabilities_recovery_and_non_consuming_queries(self):
        source=product_source()
        functions='\n'.join(function(source,n) for n in ('bNativeDetectorReady','ReconcileNativeCore','ReadNativeObservation','ShowNativeCoreStatus'))
        functions=functions.replace('int[] sample','int* sample').replace('view_as<float>','BitsFloat')
        include=(ROOT/'addons/sourcemod/scripting/include/l4d2_speedwatch_core.inc').read_text()
        constants='\n'.join(line for line in include.splitlines() if line.startswith('#define CoreCell_'))
        unit=r'''
#include <cassert>
#include <cstring>
constexpr int SPEEDWATCH_CORE_API_VERSION=2, SPEEDWATCH_CORE_SAMPLE_CELLS=48, NATIVE_DETECTOR_CAPS=7, DEBUG_GENERAL=1, SpeedWatchReason_DependencyChanged=6;
struct Runtime {bool coreAvailable=false,coreControllerAvailable=false,coreNeedsSync=true;int coreCapabilities=0;} g_Runtime;
bool library=false;int api=2,caps=7,resets=0,errors=0,reads=0,controllerState=0;
bool LibraryExists(const char*){return library;}
int SpeedWatchCore_GetApiVersion(){return api;}
int SpeedWatchCore_GetCapabilities(){return caps;}
int SpeedWatchCore_GetStatus(int);
float GetEngineTime(){return 5;}
void ResetAll(float,const char*,int){resets++;}
void DebugLog(int,const char*,const char*,...){}
void DetectionLog(const char*,const char*,...){errors++;}
void LogDebugContext(const char*){}
bool SpeedWatchCore_GetSample(int,int* sample,int length){assert(length==48);reads++;sample[10]=99;return true;}
int MaxClients=1;bool g_CoreHasSample[2]{},g_bMonitor[2]{},g_bHasSample[2]{};
int g_CoreSamples[2][48]{},g_CoreStates[2]{};
int SpeedWatchCore_GetStatus(int field){return field==3?controllerState:1;}
void ReplyToCommand(int,const char*,...){}
float BitsFloat(int bits){float f;std::memcpy(&f,&bits,4);return f;}
'''
        main=r'''
int main(){
 ReconcileNativeCore();assert(!bNativeDetectorReady()&&resets==1&&errors==1);
 library=true;g_Runtime.coreNeedsSync=true;ReconcileNativeCore();assert(bNativeDetectorReady()&&resets==2);
 g_CoreHasSample[1]=g_bMonitor[1]=true;g_CoreSamples[1][10]=77;
 int copy[48]{};assert(ReadNativeObservation(1,copy));assert(ReadNativeObservation(1,copy));
 ShowNativeCoreStatus(0);ShowNativeCoreStatus(0);
 assert(reads==2&&g_CoreSamples[1][10]==77&&resets==2);
 caps=5;ReconcileNativeCore();assert(!bNativeDetectorReady()&&resets==3);
 caps=7;ReconcileNativeCore();assert(bNativeDetectorReady()&&resets==4);
 library=false;g_Runtime.coreAvailable=false;g_Runtime.coreNeedsSync=true;
 // Removed -> Added before next reconciliation still requires a fresh reset.
 library=true;ReconcileNativeCore();assert(bNativeDetectorReady()&&resets==5);
 controllerState=2;ReconcileNativeCore();assert(!bNativeDetectorReady()&&resets==6);
 controllerState=0;ReconcileNativeCore();assert(bNativeDetectorReady()&&resets==7);
 api=1;g_Runtime.coreNeedsSync=true;ReconcileNativeCore();assert(!bNativeDetectorReady()&&resets==8);
}
'''
        run_cpp(constants+unit+functions+main)

    def test_alert_identity_snapshot_and_staff_audience(self):
        alert=function(product_source(),'SendAlert').replace('g_cvPublic.BoolValue','g_cvPublic->BoolValue')
        unit=r'''
#include <cassert>
#include <vector>
struct SpeedWatchSample {int client=1,accountId=42,userId=100;float commandsPerSecond=450,ratio=15,excess=120;int consecutiveSamples=3;};
SpeedWatchSample g_ClientSamples[5];float g_LastRate[5]{},g_LastRatio[5]{};
struct Cvar{bool BoolValue=false;} cv,*g_cvPublic=&cv;
constexpr int MaxClients=4,ADMFLAG_GENERIC=1,g_hDetectionForward=1;
std::vector<int> recipients;std::vector<double> forwarded;int prints=0;
bool IsClientInGame(int c){return c!=1;}bool IsFakeClient(int c){return c==4;}
bool CheckCommandAccess(int c,const char*,int,bool){return c==2;}
void DetectionClientLog(int,const char*,const char*,...){}
void PrintToChat(int target,const char*,...){recipients.push_back(target);}
void PrintToServer(const char*,...){prints++;}
void Call_StartForward(int){forwarded.clear();}void Call_PushCell(int n){forwarded.push_back(n);}
void Call_PushFloat(float n){forwarded.push_back(n);}
void Call_Finish(){g_ClientSamples[1].userId=999;}
'''
        main=r'''
int main(){SendAlert(1);assert(recipients.size()==1&&recipients[0]==2&&prints==1);
assert(forwarded.size()==7&&forwarded[1]==42&&forwarded[2]==100&&forwarded[3]==450);
cv.BoolValue=true;recipients.clear();SendAlert(1);assert(recipients.size()==2&&recipients[0]==2&&recipients[1]==3);}
'''
        run_cpp(unit+alert+main)

    def test_public_sample_copy_freshness_identity_and_zero_on_failure(self):
        source=product_source()
        bodies='\n'.join(function(source,n) for n in ('StoreClientSample','Native_GetClientSample'))
        bodies=bodies.replace('public any','int').replace('Handle plugin','int plugin')
        unit=r'''
#include <cassert>
#include <cstring>
struct SpeedWatchSample {int client=0,accountId=0,userId=0;float engineTime=0,commandsPerSecond=0,ratio=0,excess=0;int consecutiveSamples=0;bool inGrace=false;};
SpeedWatchSample g_ClientSamples[65],output;
bool g_bHasSample[65]{},g_bMonitor[65]{};float g_LastRate[65]{},g_LastRatio[65]{},g_Debt[65]{};int g_Strikes[65]{};
struct Runtime {bool sampleValid=true;}g_Runtime;
int MaxClients=64,nativeClient=21,currentUser=100;float now=10;bool observation=true,playing=true;
constexpr int SP_ERROR_NATIVE=1;
bool bCanObserve(){return observation;}bool bIsPlayingHuman(int){return playing;}
int GetNativeCell(int){return nativeClient;}int GetClientUserId(int){return currentUser;}
int GetSteamAccountID(int,bool){return 42;}float GetEngineTime(){return now;}
int ThrowNativeError(int,const char*,int){return -1;}
void SetNativeArray(int,const SpeedWatchSample& sample,int size){assert(size==sizeof(sample));output=sample;}
'''
        main=r'''
int main(){g_ClientSamples[21].commandsPerSecond=450;g_ClientSamples[21].ratio=15;g_Debt[21]=120;g_Strikes[21]=3;g_bMonitor[21]=true;
StoreClientSample(21,10,true);assert(Native_GetClientSample(0,2)==1&&output.inGrace&&output.accountId==42&&output.userId==100&&output.commandsPerSecond==450);
output.userId=0;assert(Native_GetClientSample(0,2)==1&&output.userId==100); // copy, not reference
now=12.01f;assert(!Native_GetClientSample(0,2)&&output.client==0&&output.commandsPerSecond==0);
now=9;assert(!Native_GetClientSample(0,2)&&output.client==0);now=10;
currentUser=101;assert(!Native_GetClientSample(0,2)&&output.userId==0);currentUser=100;
playing=false;assert(!Native_GetClientSample(0,2)&&output.client==0);playing=true;
observation=false;assert(!Native_GetClientSample(0,2));observation=true;
g_Runtime.sampleValid=false;assert(!Native_GetClientSample(0,2));g_Runtime.sampleValid=true;
g_bHasSample[21]=false;assert(!Native_GetClientSample(0,2));
nativeClient=0;assert(Native_GetClientSample(0,2)==-1);nativeClient=65;assert(Native_GetClientSample(0,2)==-1);
}
'''
        run_cpp(unit+bodies+main)

    def test_native_wire_names_match_codec_and_required_dependency(self):
        include=(ROOT/'addons/sourcemod/scripting/include/l4d2_speedwatch_core.inc').read_text()
        codec=(ROOT/'extension/api/SampleCodec.h').read_text()
        sp=dict(re.findall(r'^#define CoreCell_(\w+) (\d+)$',include,re.M))
        cpp=dict(re.findall(r'Cell(\w+) = (\d+),',codec))
        self.assertEqual(sp,cpp)
        self.assertEqual(set(map(int,sp.values())),set(range(48)))
        entry=(ROOT/'addons/sourcemod/scripting/l4d2_speedwatch.sp').read_text()
        self.assertNotIn('#undef REQUIRE_EXTENSIONS',entry)
        self.assertIn('SetFailState("SpeedWatch requires native core API',entry)
