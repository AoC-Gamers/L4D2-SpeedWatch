#include "extension.h"
#include <cstdio>
#include <iplayerinfo.h>
SpeedWatchCore g_Core;
SMEXT_LINK(&g_Core);
static_assert(sizeof(void*) == 4, "Only x86 extension builds are supported");
static_assert(sizeof(cell_t) == 4, "SourcePawn cells must be 32-bit");
bool SpeedWatchCore::SDK_OnMetamodLoad(ISmmAPI* ismm, char* error, size_t maxlen, bool) {
    GET_V_IFACE_ANY(GetServerFactory, clients, IServerGameClients, INTERFACEVERSION_SERVERGAMECLIENTS);
    GET_V_IFACE_ANY(GetServerFactory, entities, IServerGameEnts, INTERFACEVERSION_SERVERGAMEENTS);
    globals = ismm->GetCGlobals();
    return globals != nullptr;
}
bool SpeedWatchCore::Eligible(int client, speedwatch::Identity* id, int* team) const {
    if (client < 1 || client > playerhelpers->GetMaxClients() || client > speedwatch::kMaxSlots) return false;
    IGamePlayer* p = playerhelpers->GetGamePlayer(client);
    if (!p || !p->IsInGame() || p->IsFakeClient()) return false;
    IPlayerInfo* info = p->GetPlayerInfo();
    if (!info || info->IsDead() || (info->GetTeamIndex()!=2 && info->GetTeamIndex()!=3)) return false;
    if (id) { id->userId=p->GetUserId(); id->serial=p->GetSerial(); id->accountId=p->GetSteamAccountID(true); }
    if (team) *team=info->GetTeamIndex();
    return true;
}
bool SpeedWatchCore::ConfigureParticipant(int client, bool enabled) {
    speedwatch::Identity identity; int team=0;
    enabled = enabled && Eligible(client,&identity,&team);
    const auto caps = static_cast<std::uint32_t>(speedwatch::Blocks | speedwatch::TeamContext)
        | (runHooks_[client] ? speedwatch::RunAttempts : 0u);
    return observations.SetParticipant(client,identity,team,enabled,caps);
}
bool SpeedWatchCore::OwnsController(IPluginContext* context) {
    if (!controller) controller=context;
    return controller==context;
}
void SpeedWatchCore::OnPluginUnloaded(IPlugin* plugin) {
    if (plugin->GetBaseContext() == controller) {
        observations.Reset();
        for (int c=1;c<=speedwatch::kMaxSlots;++c) observations.Remove(c);
        controller=nullptr;
    }
}
std::uint32_t SpeedWatchCore::Capabilities() const {
    return (blockHook_ ? speedwatch::Blocks : 0u) | speedwatch::TeamContext
        | (runAvailable_ ? speedwatch::RunAttempts : 0u);
}
