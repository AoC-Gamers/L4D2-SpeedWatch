#include "../extension/telemetry/ObservationService.h"
#include "../extension/api/SampleCodec.h"
#include <cassert>
#include <cmath>
#include <iostream>
#include <limits>
using namespace speedwatch;
static Identity id(int slot=1) { return {slot+100,static_cast<unsigned>(slot+200),42}; }
static void start(ObservationService& s,int slot=64) {
    assert(s.SetParticipant(slot,id(slot),2,true,Blocks|RunAttempts|TeamContext));
    s.Pulse(true,1,1000000,30,1.f/30);
}
int main() {
    static_assert(sizeof(std::uint32_t)==4 && sizeof(std::uint64_t)==8,"Fixed wire integer widths");
    {
        ObservationService s; start(s);
        s.Block(64,1100000,2,5,3,false,false);
        s.Block(64,1150000,0,2,0,true,true);
        s.RunAttempt(64,1200000); s.RunAttempt(64,1200000);
        // Same client command_number could repeat: each pre-hook invocation counts once.
        assert(s.Pulse(true,1,2000000,60,1.f/30));
        auto* sample=s.Sample(64,2000000);assert(sample);
        assert(sample->counters.blocks==2 && sample->counters.newCommands==2 && sample->counters.totalCommands==7);
        assert(sample->counters.droppedPackets==3 && sample->counters.runCommandAttempts==2);
        assert(sample->counters.ignoredBlocks==1 && sample->counters.pausedBlocks==1);
        assert(sample->counters.lastInvocation==2); // Nothing claims executed commands.
        auto copy=*sample;
        assert(s.Sample(64,2000000)->sampleId==copy.sampleId);
        assert(s.Sample(64,2000000)->counters.blocks==2); // No consumption or duplicate charging.
        assert(!s.Sample(64,4000001));
        // Empty subsequent observation is distinct from previously published blocks.
        s.Pulse(true,1,3000000,90,1.f/30);
        assert(s.Sample(64,3000000)->counters.blocks==0);
        s.Pulse(false,2,3100000,93,1.f/30);assert(!s.Sample(64,3100000));
        s.RunAttempt(64,3200000);assert(!s.Active(64,3200000));
    }
    {
        ObservationService s;start(s);
        s.Block(64,1200000,-1,2,0,false,false);
        s.Block(64,1200000,3,2,0,false,false);
        s.Block(64,1200000,1,std::numeric_limits<int>::max(),0,false,false);
        s.Block(64,1200000,1,2,-1,false,false);
        s.Pulse(true,1,2000000,60,1.f/30);
        assert(s.Sample(64,2000000)->counters.discarded==4);
        assert(s.Sample(64,2000000)->quality&InvalidMetadata);
        assert(s.Sample(64,2000000)->counters.blocks==0);
        std::uint64_t n=std::numeric_limits<std::uint64_t>::max()-1;std::uint32_t q=0;
        SaturatingAdd(n,2,q);assert(n==std::numeric_limits<std::uint64_t>::max() && (q&Overflow));
    }
    {
        ObservationService s;start(s);
        s.Pulse(true,1,5000000,150,1.f/30);assert(s.Sample(64,5000000)->quality&ClockDiscontinuity);
        s.Pulse(true,1,6000000,300,1.f/30);assert(s.Sample(64,6000000)->quality&TickDiscontinuity);
        s.Pulse(true,1,7000000,330,1.f/60);assert(s.Sample(64,7000000)->quality&ClockDiscontinuity);
        s.Pulse(true,2,8000000,360,1.f/30);assert(!s.Sample(64,8000000));
        s.Pulse(true,2,9000000,390,std::numeric_limits<float>::quiet_NaN());assert(!s.Sample(64,9000000));
        s.Pulse(true,3,10000000,400,1.f/30);
        s.Pulse(true,3,9999999,430,1.f/30);assert(s.Sample(64,9999999)->quality&ClockDiscontinuity);
    }
    for(int population : {0,1,2,4,6,8,12,100}) {
        ObservationService s;
        for(int i=0;i<population;++i) assert(s.SetParticipant(i+50,id(i+50),i%2+2,true,Blocks));
        assert(s.Count()==static_cast<unsigned>(population));
        assert(!s.SetParticipant(257,id(),2,true,Blocks));
        assert(s.SetParticipant(250,id(),1,true,Blocks));assert(!s.Active(250,100));
        assert(s.SetParticipant(251,id(),2,false,Blocks));
    }
    {
        ObservationService s;start(s);s.RunAttempt(64,1200000);
        s.Pulse(true,1,2000000,60,1.f/30);auto generation=s.Sample(64,2000000)->generation;
        Identity newer=id(64);++newer.serial;
        s.SetParticipant(64,newer,2,true,Blocks);assert(!s.Sample(64,2000000));
        s.RunAttempt(64,2200000);s.Pulse(true,1,3000000,90,1.f/30);
        assert(s.Sample(64,3000000)->generation!=generation && s.Sample(64,3000000)->counters.runCommandAttempts==0);
        s.Remove(64);assert(s.Count()==0 && !s.Sample(64,3000000));
    }
    {
        Snapshot s;s.sampleId=0xfedcba9876543210ULL;s.identity=id();s.counters.runCommandAttempts=0x123456789ULL;
        s.startUs=1000000;s.endUs=2000000;s.interval=1.f/30;s.capabilities=Blocks|RunAttempts;
        std::int32_t out[kSampleCells+2];for(auto& n:out)n=0x1234;
        assert(!EncodeSample(&s,2,out,kSampleCells));assert(out[0]==0x1234);
        assert(!EncodeSample(&s,1,out,kSampleCells-1));assert(out[0]==0x1234);
        assert(EncodeSample(&s,1,out,kSampleCells+2));assert(out[kSampleCells]==0x1234 && out[kSampleCells+1]==0x1234);
        assert(static_cast<std::uint32_t>(out[10])==0x76543210u && static_cast<std::uint32_t>(out[11])==0xfedcba98u);
        assert(out[33]==0x23456789 && out[34]==1 && out[3]==3);
        assert(!EncodeSample(nullptr,1,out,kSampleCells));assert(out[0]==1 && out[1]==kSampleCells && out[33]==0);
        assert(!EncodeSample(&s,1,nullptr,kSampleCells));
    }
    std::cout<<"ObservationService/codec tests passed ("<<sizeof(void*)*8<<"-bit host). No SRCDS/SourceHook claims.\n";
}
