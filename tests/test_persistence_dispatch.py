"""Production notification queue with SourceMod forward/array doubles, not VM execution."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from test_participant_policy import function, product_source

ROOT=Path(__file__).resolve().parents[1]

class PersistenceDispatchTests(unittest.TestCase):
    def test_identity_snapshot_order_and_reentrant_terminal(self):
        compiler=shutil.which('c++')
        if not compiler: self.skipTest('C++ compiler absent')
        source=product_source()
        structs=[]
        for name in ('DetectionEpisode','DetectionStateEvent'):
            start=source.index('enum struct '+name); end=source.index('\n}',start)+2
            structs.append(source[start:end].replace('enum struct','struct')+';')
        body='\n'.join(function(source,n) for n in ('QueueDetectionEvent','QueueDetectionPersistence','FlushDetectionEvents'))
        body=body.replace('g_DetectionEvents.','g_DetectionEvents->')
        prelude=r'''
#include <cassert>
#include <vector>
constexpr int SpeedWatchDetection_Active=0, SpeedWatchDetection_Interrupted=2;
constexpr int SpeedWatchReason_None=0, SpeedWatchReason_ObservationReset=18;
using SpeedWatchDetectionState=int; using SpeedWatchDetectionReason=int;
'''
        adapters=r'''
DetectionEpisode g_Detections[65]{};
struct Array {
 std::vector<DetectionStateEvent> rows; int Length=0;
 void PushArray(const DetectionStateEvent& event,int){rows.push_back(event);Length=rows.size();}
 void GetArray(int index,DetectionStateEvent& event,int){event=rows.at(index);reads++;}
 int reads=0,clears=0;
 void Clear(){rows.clear();Length=0;clears++;}
} storage;
Array* g_DetectionEvents=&storage;
struct {bool dispatchingDetectionEvents=false;} g_Runtime;
constexpr int g_hDetectionStateForward=1,g_hDetectionPersistenceForward=2;
struct Forward {int type;std::vector<double> args;} current;
std::vector<Forward> calls;
void DetectionLog(const char*,const char*,...){}
void Call_StartForward(int type){current={type,{}};}
void Call_PushCell(int value){current.args.push_back(value);}
void Call_PushFloat(float value){current.args.push_back(value);}
void Call_Finish();
'''
        main=r'''
void Call_Finish(){
 calls.push_back(current);
 if(current.type==g_hDetectionPersistenceForward){
  // Emulate a consumer resetting the observation inside its persistence callback.
  QueueDetectionEvent(21,SpeedWatchDetection_Interrupted,SpeedWatchReason_ObservationReset);
  assert(!FlushDetectionEvents());
 }
}
int main(){
 g_Detections[21].accountId=42;g_Detections[21].userId=100;
 QueueDetectionEvent(21,SpeedWatchDetection_Active,SpeedWatchReason_None);
 g_Detections[21].persistenceTime=30.25f;QueueDetectionPersistence(21);
 g_Detections[21].userId=101; // A queued marker must retain its original identity.
 assert(FlushDetectionEvents());
 assert(calls.size()==3&&calls[0].type==1&&calls[1].type==2&&calls[2].type==1);
 assert(calls[1].args.size()==5);
 assert(calls[1].args[0]==21&&calls[1].args[1]==42&&calls[1].args[2]==100);
 assert(calls[1].args[3]==1&&calls[1].args[4]==30.25);
 assert(calls[2].args[3]==SpeedWatchDetection_Interrupted);
 assert(storage.Length==0&&!g_Runtime.dispatchingDetectionEvents&&storage.reads==3&&storage.clears==1);
 assert(!FlushDetectionEvents());
 // A large FIFO drain reads every event once and clears once, without per-item shifts.
 for(int i=0;i<2048;i++) QueueDetectionEvent(21,SpeedWatchDetection_Active,SpeedWatchReason_None);
 assert(FlushDetectionEvents());
 assert(storage.Length==0&&storage.reads==2051&&storage.clears==2&&calls.size()==2051);
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            cpp=Path(tmp)/'queue.cpp'; binary=Path(tmp)/'queue'
            cpp.write_text(prelude+'\n'.join(structs)+adapters+body+main)
            subprocess.run([compiler,'-std=c++17','-Wall','-Wextra','-Werror',str(cpp),'-o',str(binary)],check=True,timeout=30)
            subprocess.run([str(binary)],check=True,timeout=5)
