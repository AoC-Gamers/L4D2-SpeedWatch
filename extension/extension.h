#pragma once
#include "smsdk_ext.h"
#include "telemetry/ObservationService.h"
#include <array>
class CUserCmd;
class IMoveHelper;
class SpeedWatchCore final : public SDKExtension, public IClientListener, public IPluginsListener {
public:
    bool SDK_OnMetamodLoad(ISmmAPI*, char*, size_t, bool) override;
    bool SDK_OnLoad(char*, size_t, bool) override;
    void SDK_OnUnload() override;
    void OnClientPutInServer(int client) override;
    void OnClientDisconnecting(int client) override;
    void OnPluginUnloaded(IPlugin* plugin) override;
    bool ConfigureParticipant(int client, bool enabled);
    bool OwnsController(IPluginContext* context);
    std::uint32_t Capabilities() const;
    speedwatch::ObservationService observations;
    CGlobalVars* globals = nullptr;
    IServerGameClients* clients = nullptr;
    IServerGameEnts* entities = nullptr;
    IPluginContext* controller = nullptr;
    bool Eligible(int client, speedwatch::Identity* identity = nullptr, int* team = nullptr) const;
private:
    float OnProcessUsercmds(edict_t*, bf_read*, int, int, int, bool, bool);
    void OnRunCommand(CUserCmd*, IMoveHelper*);
    void OnLevelShutdown();
    std::array<int, speedwatch::kMaxSlots+1> runHooks_{};
    IGameConfig* gameConfig_ = nullptr;
    int blockHook_ = 0, shutdownHook_ = 0;
    bool runAvailable_ = false, listening_ = false;
};
extern SpeedWatchCore g_Core;
extern const sp_nativeinfo_t g_CoreNatives[];
std::uint64_t SpeedWatchNowUs();
