"""Productive context bodies with property/logger doubles, not SourceMod or SRCDS."""
from pathlib import Path
import re
import unittest
from test_observation_contract import run_cpp
from test_participant_policy import function

ROOT=Path(__file__).resolve().parents[1]
DIRECTORY=ROOT/'addons/sourcemod/scripting/l4d2_speedwatch'

class MovementContextTests(unittest.TestCase):
    def test_productive_capture_gates_snapshot_properties_and_bhop_configuration(self):
        source=(DIRECTORY/'context.sp').read_text()
        structs=[]
        for name in ('MovementProfile','MovementContext'):
            start=source.index('enum struct '+name);end=source.index('\n}',start)+2
            struct=source[start:end].replace('enum struct','struct')+';'
            struct=re.sub(r'^    ((?:bool|int|float|char) \w+(?:\[\d+\])?);',r'    \1{};',struct,flags=re.M)
            structs.append(struct)
        bodies='\n'.join(function(source,n) for n in ('ContextConVarInt','CaptureMovementProfile','ConfiguredBhopPolicy','ContextSendInt','ContextFinite','ContextFloat','ContextPinState','CaptureMovementContext','WriteMovementContext','CaptureSampleContext'))
        bodies=function((DIRECTORY/'observation.sp').read_text(),'bIsPlayingHuman')+'\n'+bodies
        bodies=bodies.replace('const char[]','const char*').replace('MovementProfile profile','MovementProfile& profile').replace('MovementContext context','MovementContext& context')
        bodies=bodies.replace('value.IntValue','value->IntValue').replace('mode.GetString','mode->GetString').replace('null','nullptr').replace('view_as<int>','Cell')
        bodies=bodies.replace('static const char properties[][]','static const char* properties[]').replace('i < sizeof(properties)','i < static_cast<int>(sizeof(properties)/sizeof(properties[0]))')
        constants='\n'.join(line for line in (ROOT/'addons/sourcemod/scripting/include/l4d2_speedwatch_core.inc').read_text().splitlines() if line.startswith('#define CoreCell_'))
        adapters=r'''
#include <cassert>
#include <cmath>
#include <cstring>
#include <cstdio>
#include <cstdarg>
#include <map>
#include <string>
#include <vector>
constexpr int MaxClients=64,FL_ONGROUND=1,FL_DUCKING=2,DEBUG_SAMPLES=4;
enum PropType {Prop_Send,Prop_Data};
int propertyCalls=0,findCalls=0;
bool g_bHuman[65]{},g_CoreHasSample[65]{},inGame[65]{},alive[65]{};
int g_CoreSamples[65][48]{},teams[65]{},users[65]{},flags[65]{},health[65]{};
float vx=300,vy=400;
std::map<std::string,float> props[65];
struct Cvar {int IntValue=0;std::string text;void GetString(char* out,int n){std::snprintf(out,n,"%s",text.c_str());}};
using ConVar=Cvar*;std::map<std::string,Cvar> cvars;
ConVar FindConVar(const char* key){findCalls++;auto i=cvars.find(key);return i==cvars.end()?nullptr:&i->second;}
bool IsClientInGame(int c){return inGame[c];}bool IsPlayerAlive(int c){return alive[c];}
int GetClientTeam(int c){return teams[c];}int GetClientUserId(int c){return users[c];}
int GetGameTickCount(){return 900;}int GetEntityFlags(int c){propertyCalls++;return flags[c];}
int GetEntityMoveType(int){propertyCalls++;return 2;}int GetClientHealth(int c){propertyCalls++;return health[c];}
bool HasEntProp(int c,PropType,const char* p){propertyCalls++;return props[c].count(p);}
int GetEntProp(int c,PropType,const char* p){propertyCalls++;return props[c].at(p);}
int GetEntPropEnt(int c,PropType,const char* p){propertyCalls++;return props[c].at(p);}
float GetEntPropFloat(int c,PropType,const char* p){propertyCalls++;return props[c].at(p);}
void GetEntPropVector(int,PropType,const char*,float* v){propertyCalls++;v[0]=vx;v[1]=vy;v[2]=999;}
float SquareRoot(float f){return std::sqrt(f);}
int Cell(float f){int n;std::memcpy(&n,&f,4);return n;}int Cell(int n){return n;}
void strcopy(char* out,int n,const char* value){std::snprintf(out,n,"%s",value);}
void Format(char* out,int n,const char* fmt,...){va_list ap;va_start(ap,fmt);std::vsnprintf(out,n,fmt,ap);va_end(ap);}
struct Log {void* file=nullptr;bool samples=false;int flushes=0;std::vector<std::string> lines;
 bool bDebug(int){return file&&samples;}void Write(const char*,const char* text){lines.push_back(text);}void Flush(){flushes++;}
}g_Log;
'''
        main=r'''
int main(){
 MovementProfile profile;MovementContext context;
 // No logger or diagnostic category: no ConVar/property work, including alert sink failure.
 CaptureSampleContext(21,10,false,profile,context);CaptureSampleContext(21,10,true,profile,context);
 assert(findCalls==0&&propertyCalls==0&&!profile.captured&&!context.captured);
 g_Log.file=&g_Log;CaptureSampleContext(21,10,false,profile,context);assert(findCalls==0&&propertyCalls==0);
 for(int c : {21,22,23,64}){g_bHuman[c]=g_CoreHasSample[c]=inGame[c]=alive[c]=true;users[c]=100+c;teams[c]=2;}
 teams[22]=3;alive[22]=false;teams[23]=1;g_bHuman[64]=false;
 flags[21]=FL_ONGROUND|FL_DUCKING;health[21]=51;
 props[21]={{"m_nWaterLevel",2},{"m_isIncapacitated",0},{"m_isHangingFromLedge",0},{"m_bAdrenalineActive",1},{"m_healthBuffer",23.5f},{"m_flMaxspeed",250},{"m_vecAbsVelocity",1},
 {"m_tongueOwner",-1},{"m_pounceAttacker",-1},{"m_jockeyAttacker",-1},{"m_carryAttacker",-1},{"m_pummelAttacker",-1}};
 cvars["mp_gamemode"].text="versus\nunsafe mode";
 cvars["simple_antibhop_enable"].IntValue=1;cvars["bhop_allow_survivor"].IntValue=0;cvars["bhop_except_si_flags"].IntValue=64;
 g_CoreSamples[21][8]=9;g_CoreSamples[21][9]=3;g_CoreSamples[21][10]=77;g_CoreSamples[21][11]=1;g_CoreSamples[21][45]=123;g_CoreSamples[21][46]=2;
 // Alert context is captured with debug off, without a periodic log.
 CaptureSampleContext(21,10,true,profile,context);
 assert(profile.captured&&profile.survivors==1&&profile.infected==1);
 assert(std::string(profile.mode)=="versus_unsafe_mode"&&profile.survivorLimit==-1);
 assert(context.captured&&context.client==21&&context.userId==121&&context.speed2d==500&&context.pinned==0&&context.healthBufferRaw==23.5f&&context.bhopConfig==1);
 assert(context.windowLow==77&&context.coreHigh==2&&g_Log.lines.empty());
 int capturedReads=propertyCalls,profileReads=findCalls;
 // Simulate an Active consumer changing the entity/window before alert delivery.
 users[21]=999;health[21]=1;g_CoreSamples[21][10]=88;props[21]["m_flMaxspeed"]=900;
 WriteMovementContext(context,profile,true);assert(propertyCalls==capturedReads&&findCalls==profileReads&&g_Log.flushes==1);
 auto line=g_Log.lines.back();
 for(const char* field : {"schema=2 scope=sample_end source=alert","userid=121","health=51","speed2d=500.00","maxspeed_prop=250.00","window=00000001:0000004d","core_instance=00000002:0000007b","bhop_config=1"})assert(line.find(field)!=std::string::npos);
 assert(line.find('\n')==std::string::npos);
 // Debug samples reuse one evaluation profile; the player's snapshot is always local.
 g_Log.samples=true;MovementContext next;vx=600;vy=800;CaptureSampleContext(21,11,false,profile,next);
 assert(next.speed2d==1000&&next.userId==999&&findCalls==profileReads&&g_Log.lines.size()==2);
 auto before=g_Log.lines.size();g_Log.file=nullptr;WriteMovementContext(next,profile,true);assert(g_Log.lines.size()==before);
 // Spectators, bots, dead subjects, slots out of range and no native observation: no physical reads.
 capturedReads=propertyCalls;
 for(int c : {0,65,22,23,64}){MovementContext invalid;CaptureMovementContext(c,12,profile,invalid);assert(!invalid.captured);}
 g_CoreHasSample[21]=false;MovementContext absent;CaptureMovementContext(21,12,profile,absent);assert(!absent.captured&&propertyCalls==capturedReads);g_CoreHasSample[21]=true;
 // Missing/NaN values remain unknown; a single pin owner suffices, missing owners do not prove free movement.
 props[21].clear();props[21]["m_vecAbsVelocity"]=1;vx=std::nanf("");
 MovementContext missing;CaptureMovementContext(21,12,profile,missing);
 assert(missing.captured&&missing.speed2d==-1&&missing.maxspeedProperty==-1&&missing.pinned==-1&&missing.waterLevel==-1);
 props[21]["m_jockeyAttacker"]=22;CaptureMovementContext(21,12,profile,missing);assert(missing.pinned==1);
 props[21]["m_flMaxspeed"]=std::nanf("");assert(ContextFloat(21,Prop_Data,"m_flMaxspeed")==-1);
 // Configuration is declarative, not an assertion that anti-bhop ran.
 for(int cls=1;cls<=6;cls++){profile.infectedBhopFlags=1<<(cls-1);assert(ConfiguredBhopPolicy(3,cls,profile)==2);profile.infectedBhopFlags=0;assert(ConfiguredBhopPolicy(3,cls,profile)==1);}
 profile.infectedBhopFlags=64;assert(ConfiguredBhopPolicy(3,8,profile)==2&&ConfiguredBhopPolicy(3,7,profile)==-1);
 profile.antiBhopEnabled=-1;assert(ConfiguredBhopPolicy(2,0,profile)==-1);profile.antiBhopEnabled=0;assert(ConfiguredBhopPolicy(2,0,profile)==0);
}
'''
        run_cpp(constants+adapters+'\n'.join(structs)+bodies+main)

    def test_capture_precedes_episode_forwards_and_manifest_includes_module(self):
        source=(DIRECTORY/'observation.sp').read_text()
        capture=source.index('CaptureSampleContext(client, now, g_Strikes')
        self.assertLess(capture,source.index('UpdateDetectionEpisode(client,'))
        self.assertLess(capture,source.index('SendAlert(client, context, profile)'))
        import json
        manifest=json.loads((ROOT/'plugin-package-map.json').read_text())
        self.assertIn('context.sp',manifest['artifact']['addons']['sourcemod']['scripting']['l4d2_speedwatch']['files'])
