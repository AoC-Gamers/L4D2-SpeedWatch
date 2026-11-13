#include "../extension.h"
#include <cstdio>
#include <string>
// Exact L4D2 eiface.h ABI; buf is an opaque borrowed pointer and is never read.
SH_DECL_HOOK7(IServerGameClients, ProcessUsercmds, SH_NOATTRIB, 0, float,
    edict_t*, bf_read*, int, int, int, bool, bool);
SH_DECL_HOOK0_void(IServerGameDLL, LevelShutdown, SH_NOATTRIB, 0);
// Same prototype and named SDKTools gamedata key as SDKTools hooks.cpp.
SH_DECL_MANUALHOOK2_void(SpeedWatchRunCommand, 0, 0, 0, CUserCmd*, IMoveHelper*);
bool SpeedWatchCore::SDK_OnLoad(char* error, size_t maxlen, bool) {
    if (!globals || !clients || !entities || std::string(g_pSM->GetGameFolderName()) != "left4dead2") {
        std::snprintf(error,maxlen,"Requires L4D2 x86 game interfaces"); return false;
    }
    if (playerhelpers->GetMaxClients() > speedwatch::kMaxSlots) {
        std::snprintf(error,maxlen,"Server exceeds supported slot capacity (%d)",speedwatch::kMaxSlots); return false;
    }
    blockHook_ = SH_ADD_HOOK(IServerGameClients,ProcessUsercmds,clients,SH_MEMBER(this,&SpeedWatchCore::OnProcessUsercmds),false);
    shutdownHook_ = SH_ADD_HOOK(IServerGameDLL,LevelShutdown,gamedll,SH_MEMBER(this,&SpeedWatchCore::OnLevelShutdown),false);
    if (!blockHook_ || !shutdownHook_) { SDK_OnUnload(); std::snprintf(error,maxlen,"Cannot install interface hooks"); return false; }
    char confError[256]{};
    if (gameconfs->LoadGameConfigFile("sdktools.games",&gameConfig_,confError,sizeof(confError))) {
        int offset=0;
        if (gameConfig_->GetOffset("PlayerRunCmd",&offset) && offset>0) {
            SH_MANUALHOOK_RECONFIGURE(SpeedWatchRunCommand,offset,0,0); runAvailable_=true;
        }
    }
    // Missing run offset degrades to block metadata; it does not prevent load.
    sharesys->AddNatives(myself,g_CoreNatives);
    sharesys->RegisterLibrary(myself,"l4d2_speedwatch_core");
    playerhelpers->AddClientListener(this); plsys->AddPluginsListener(this); listening_=true;
    for (int c=1;c<=playerhelpers->GetMaxClients();++c) OnClientPutInServer(c);
    return true;
}
void SpeedWatchCore::OnClientPutInServer(int client) {
    if (client<1 || client>speedwatch::kMaxSlots) return;
    OnClientDisconnecting(client);
    IGamePlayer* player=playerhelpers->GetGamePlayer(client);
    if (!runAvailable_ || !player || !player->IsInGame() || player->IsFakeClient()) return;
    edict_t* edict=player->GetEdict();
    CBaseEntity* entity=edict ? entities->EdictToBaseEntity(edict) : nullptr;
    if (entity) runHooks_[client]=SH_ADD_MANUALHOOK(SpeedWatchRunCommand,entity,SH_MEMBER(this,&SpeedWatchCore::OnRunCommand),false);
}
void SpeedWatchCore::OnClientDisconnecting(int client) {
    if (client<1 || client>speedwatch::kMaxSlots) return;
    if (runHooks_[client]) { SH_REMOVE_HOOK_ID(runHooks_[client]); runHooks_[client]=0; }
    observations.Remove(client);
}
float SpeedWatchCore::OnProcessUsercmds(edict_t* player, bf_read*, int num, int total, int dropped, bool ignore, bool paused) {
    IGamePlayer* p=playerhelpers->GetGamePlayer(player);
    if (p && observations.Active(p->GetIndex(),SpeedWatchNowUs())) {
        if (Eligible(p->GetIndex())) observations.Block(p->GetIndex(),SpeedWatchNowUs(),num,total,dropped,ignore,paused,globals->tickcount);
        else observations.Remove(p->GetIndex());
    }
    RETURN_META_VALUE(MRES_IGNORED,0.0f);
}
void SpeedWatchCore::OnRunCommand(CUserCmd*, IMoveHelper*) {
    auto* entity=META_IFACEPTR(CBaseEntity);
    edict_t* edict=entities->BaseEntityToEdict(entity);
    IGamePlayer* p=edict ? playerhelpers->GetGamePlayer(edict) : nullptr;
    if (p && observations.Active(p->GetIndex(),SpeedWatchNowUs())) {
        if (Eligible(p->GetIndex())) observations.RunAttempt(p->GetIndex(),SpeedWatchNowUs(),globals->tickcount);
        else observations.Remove(p->GetIndex());
    }
    // No post hook, no claim that the original or a simulation step executed.
    RETURN_META(MRES_IGNORED);
}
void SpeedWatchCore::OnLevelShutdown() {
    observations.Reset();
    for (int c=1;c<=speedwatch::kMaxSlots;++c) OnClientDisconnecting(c);
    RETURN_META(MRES_IGNORED);
}
void SpeedWatchCore::SDK_OnUnload() {
    observations.Reset(); controller=nullptr;
    if (listening_) { playerhelpers->RemoveClientListener(this); plsys->RemovePluginsListener(this); listening_=false; }
    for (int c=1;c<=speedwatch::kMaxSlots;++c) OnClientDisconnecting(c);
    if (blockHook_) { SH_REMOVE_HOOK_ID(blockHook_); blockHook_=0; }
    if (shutdownHook_) { SH_REMOVE_HOOK_ID(shutdownHook_); shutdownHook_=0; }
    if (gameConfig_) { gameconfs->CloseGameConfigFile(gameConfig_); gameConfig_=nullptr; }
    runAvailable_=false;
}
