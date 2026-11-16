"""Production log formatting/gates with C++ doubles, not an SP VM/runtime test.

SP properties/arrays are adapted; VFormat is replaced by C varargs. Its SP argument
indices are checked separately. No disk IO, provider natives or server required.
"""
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest
from test_participant_policy import function

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'addons/sourcemod/scripting'

PRELUDE = r'''
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <string>
#include <vector>
constexpr int PLATFORM_MAX_PATH=260, DEBUG_DEFAULT=15, DEBUG_SAMPLES=4;
constexpr int SPEEDWATCH_CORE_API_VERSION=2;
const char* SPEEDWATCH_VERSION="0.12.0";
constexpr auto null=nullptr;
int MaxClients=64, mapCalls=0;
bool g_CoreHasSample[65]{};
int g_CoreSamples[65][48]{};
std::string currentMap="c2m1_highway";
struct Cvar { bool BoolValue=true; int IntValue=1; float FloatValue=1; };
using ConVar=Cvar*;
Cvar cvDebug{}, cvMask{true,15,15}, cvEnabled{}, cvRate{true,1,1.1f}, cvBurst{true,2,2};
Cvar cvSamples{true,3,3}, cvGrace{true,5,5}, cvCooldown{true,30,30}, cvRecovery{true,5,5}, cvPublic{};
Cvar *g_cvDebug=&cvDebug, *g_cvDebugMask=&cvMask, *g_cvEnabled=&cvEnabled, *g_cvRate=&cvRate;
Cvar *g_cvBurst=&cvBurst, *g_cvSamples=&cvSamples, *g_cvGrace=&cvGrace, *g_cvCooldown=&cvCooldown;
Cvar *g_cvRecoveryTime=&cvRecovery, *g_cvPublic=&cvPublic;
struct Runtime { int observationGeneration=9, coreCapabilities=7; bool mapLoaded=true, lateLoad=false, coreAvailable=true, coreNeedsSync=false; } g_Runtime;
void Format(char* out, int length, const char* format, ...) {
    char tmp[4096]; va_list args; va_start(args,format); std::vsnprintf(tmp,sizeof(tmp),format,args); va_end(args);
    std::snprintf(out,length,"%s",tmp);
}
void strcopy(char* out,int length,const char* value) { std::snprintf(out,length,"%s",value); }
void FormatTime(char* out,int length,const char*) { strcopy(out,length,"2026-11-13 12:00:00"); }
void GetCurrentMap(char* out,int length) { ++mapCalls; strcopy(out,length,currentMap.c_str()); }
float GetTickInterval() { return 1.f/30; }
int GetClientUserId(int client) { return client+100; }
struct FileMock {
    std::vector<std::string> lines;
    bool WriteLine(const char* format, ...) {
        char out[4096]; va_list args; va_start(args,format); std::vsnprintf(out,sizeof(out),format,args); va_end(args);
        lines.push_back(out); return true;
    }
} file;
'''

MAIN = r'''
int main() {
    g_Log.file=&file;
    g_cvDebug->BoolValue=false;
    LogDebugContext("off"); DebugClientLog(4,"samples",42,"event=probe");
    assert(file.lines.empty() && mapCalls==0);
    g_cvDebug->BoolValue=true; g_cvDebugMask->IntValue=0;
    LogDebugContext("mask_zero"); assert(file.lines.empty() && mapCalls==0);
    g_cvDebugMask->IntValue=16;
    LogDebugContext("reserved"); assert(file.lines.empty() && mapCalls==0);
    // Context must be present when only the samples category is selected.
    g_cvDebugMask->IntValue=4;
    OnDebugSettingChanged(g_cvDebugMask,"0","4");
    assert(file.lines.size()==1 && mapCalls==1);
    auto context=file.lines.back();
    for (const char* key : {"event=debug_context", "trigger=debug_setting", "version=0.12.0", "map=c2m1_highway",
        "flags=4", "backend=native", "caps=7", "api_expected=2", "rate=1.100", "cooldown=30.000", "recovery=5.000"})
        assert(context.find(key)!=std::string::npos);
    assert(g_Runtime.observationGeneration==9 && g_Log.evaluation==42);
    g_Runtime.mapLoaded=false;
    LogDebugContext("plugin_start");
    assert(mapCalls==1 && file.lines.back().find("map=unavailable")!=std::string::npos);
    // Long map names must not silently drop the final configuration fields.
    g_Runtime.mapLoaded=true; currentMap=std::string(255,'m'); LogDebugContext("configs_executed");
    assert(file.lines.back().find("interval=0.033333")!=std::string::npos);
    g_CoreHasSample[42]=true;
    g_CoreSamples[42][5]=142; g_CoreSamples[42][8]=9; g_CoreSamples[42][9]=17;
    g_CoreSamples[42][11]=static_cast<int>(0x80000000u); g_CoreSamples[42][10]=static_cast<int>(0xffffffffu);
    DebugClientLog(4,"samples",42,"event=client_sample count=%d",30);
    auto sample=file.lines.back();
    assert(sample.find("window_epoch=9 generation=17 window=80000000:ffffffff")!=std::string::npos);
    assert(sample.find("count=30")!=std::string::npos);
    // Mandatory alerts keep correlation even when debug is disabled.
    g_cvDebug->BoolValue=false;
    DetectionClientLog(42,"detections","event=alert count=%d",30);
    auto alert=file.lines.back();
    assert(alert.find("window_epoch=9 generation=17 window=80000000:ffffffff")!=std::string::npos);
    for (const auto* line : {&sample,&alert})
        assert(line->find("session=test-session evaluation=0000002a observation_epoch=9")!=std::string::npos);
    char out[128];
    FormatNativeLogContext(42,999,out,sizeof(out)); assert(std::string(out)=="window_available=0");
    g_CoreHasSample[42]=false;
    FormatNativeLogContext(42,142,out,sizeof(out)); assert(std::string(out)=="window_available=0");
    auto count=file.lines.size(); g_Log.file=nullptr;
    LogDebugContext("no_file"); DetectionClientLog(42,"detections","event=alert");
    assert(file.lines.size()==count);
}
'''


class DebugLoggingTests(unittest.TestCase):
    def test_context_correlation_and_disabled_gates(self):
        compiler=shutil.which('c++')
        if not compiler:
            self.skipTest('C++ compiler absent')
        log=(SCRIPTS/'l4d2_speedwatch/logging.sp').read_text()
        native=(SCRIPTS/'l4d2_speedwatch/native_client.sp').read_text()
        methods=log.replace('\n    ','\n')
        unit=PRELUDE+'\nstruct RuntimeLog {\nFileMock* file=nullptr; bool dirty=false; int evaluation=42; char session[32]="test-session";\n'
        unit+='void Fail(const char*) { file=nullptr; } void Flush() {}\n'
        unit+='\n'.join(function(methods,n) for n in ('bDebug','Write'))+'\n} g_Log;\n'
        unit+=function(native,'FormatNativeLogContext')+'\n'
        unit+='\n'.join(function(log,n).removeprefix('public ') for n in ('DebugClientLog','DetectionClientLog','LogDebugContext','OnDebugSettingChanged'))
        unit=unit.replace('any...', '...').replace('const char[]','const char*').replace('char[] text','char* text')
        unit=re.sub(r'g_cv(\w+)\.',r'g_cv\1->',unit)
        unit=unit.replace('this.file.WriteLine','this->file->WriteLine').replace('this.', 'this->')
        constants='\n'.join(line for line in (SCRIPTS/'include/l4d2_speedwatch_core.inc').read_text().splitlines() if line.startswith('#define CoreCell_'))
        unit=constants+'\n'+unit
        unit=re.sub(r'    VFormat\(message, sizeof\(message\), format, [45]\);',
            '    va_list args; va_start(args,format); std::vsnprintf(message,sizeof(message),format,args); va_end(args);',unit)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'logging.cpp'; binary=Path(tmp)/'logging'
            source.write_text(unit+MAIN)
            subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror','-Wno-unused-parameter',str(source),'-o',str(binary)],check=True,timeout=30)
            subprocess.run([str(binary)],check=True,timeout=5)

    def test_sourcepawn_vararg_indices_and_pure_debug_hook(self):
        log=(SCRIPTS/'l4d2_speedwatch/logging.sp').read_text()
        for name,index in [('DebugLog',4),('DetectionLog',3),('DebugClientLog',5),('DetectionClientLog',4)]:
            self.assertIn(f'VFormat(message, sizeof(message), format, {index});',function(log,name))
        hook=function(log,'OnDebugSettingChanged')
        self.assertNotIn('Reset',hook)
        self.assertNotIn('Pulse',hook)
        self.assertNotIn('observationGeneration',hook)
