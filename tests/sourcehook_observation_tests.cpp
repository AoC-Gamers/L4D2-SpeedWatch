// Real SourceHook chain, synthetic object. Not a game ABI or SRCDS test.
#include <sourcehook.h>
#include <sourcehook_impl.h>
#include <cassert>
#include <iostream>
#include "../extension/telemetry/ObservationService.h"
SourceHook::ISourceHook* g_SHPtr=nullptr;
SourceHook::Plugin g_PLID=1;
class SyntheticPlayer {
public:
    virtual void Run(void*,void*) { ++original; }
    int original=0;
};
SH_DECL_HOOK2_void(SyntheticPlayer,Run,SH_NOATTRIB,0,void*,void*);
speedwatch::ObservationService service;
bool block=false,reenter=false;
int posts=0;
void Observe(void*,void*) {
    service.RunAttempt(64,1200000);
    RETURN_META(MRES_IGNORED);
}
void SdkToolsLikeFilter(void*,void*) {
    if (block) RETURN_META(MRES_SUPERCEDE);
    RETURN_META(MRES_IGNORED);
}
void Post(void*,void*) { ++posts; RETURN_META(MRES_IGNORED); }
SyntheticPlayer* current=nullptr;
void Reentrant(void*,void*) {
    if (reenter) { reenter=false; current->Run(nullptr,nullptr); }
    RETURN_META(MRES_IGNORED);
}
#if defined(__GNUC__)
__attribute__((noinline))
#endif
void Invoke(SyntheticPlayer* p) { p->Run(nullptr,nullptr); }
int main() {
    g_SHPtr=new SourceHook::Impl::CSourceHookImpl();
    SyntheticPlayer player;current=&player;
    service.SetParticipant(64,{101,201,42},2,true,speedwatch::RunAttempts);
    service.Pulse(true,1,1000000,30,1.f/30);
    const auto observation=SH_ADD_HOOK(SyntheticPlayer,Run,&player,SH_STATIC(Observe),false);
    const auto filter=SH_ADD_HOOK(SyntheticPlayer,Run,&player,SH_STATIC(SdkToolsLikeFilter),false);
    const auto post=SH_ADD_HOOK(SyntheticPlayer,Run,&player,SH_STATIC(Post),true);
    const auto nested=SH_ADD_HOOK(SyntheticPlayer,Run,&player,SH_STATIC(Reentrant),false);
    assert(observation && filter && post && nested);
    Invoke(&player);assert(player.original==1 && posts==1);
    block=true;Invoke(&player);assert(player.original==1 && posts==2);
    // A post callback did happen, even though the original was SUPERCEDEd.
    block=false;reenter=true;Invoke(&player);assert(player.original==3 && posts==4);
    service.Pulse(true,1,2000000,60,1.f/30);
    assert(service.Sample(64,2000000)->counters.runCommandAttempts==4);
    assert(service.Sample(64,2000000)->counters.lastInvocation==4);
    SH_REMOVE_HOOK_ID(observation);SH_REMOVE_HOOK_ID(filter);SH_REMOVE_HOOK_ID(post);SH_REMOVE_HOOK_ID(nested);
    Invoke(&player);assert(player.original==4 && posts==4);
    delete g_SHPtr;
    std::cout<<"SourceHook: SUPERCEDE, post, reentrancy and teardown verified on synthetic object.\n";
}
