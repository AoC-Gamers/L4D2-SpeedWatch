#include "../extension.h"
#include "SampleCodec.h"
#include <limits>
namespace {
cell_t Version(IPluginContext*, const cell_t*) { return speedwatch::kApiVersion; }
cell_t Caps(IPluginContext*, const cell_t*) { return g_Core.Capabilities(); }
bool Controller(IPluginContext* c) {
    if (g_Core.OwnsController(c)) return true;
    c->ThrowNativeError("Observation already owned by another plugin"); return false;
}
cell_t Pulse(IPluginContext* c,const cell_t* p) {
    if (!Controller(c)) return 0;
    return g_Core.observations.Pulse(p[1]!=0,static_cast<std::uint32_t>(p[2]),SpeedWatchNowUs(),
        g_Core.globals->tickcount,g_Core.globals->interval_per_tick);
}
cell_t Participant(IPluginContext* c,const cell_t* p) {
    if (!Controller(c)) return 0;
    if (p[1]<1 || p[1]>playerhelpers->GetMaxClients() || p[1]>speedwatch::kMaxSlots) return c->ThrowNativeError("Invalid client index %d",p[1]);
    return g_Core.ConfigureParticipant(p[1],p[2]!=0);
}
cell_t Sample(IPluginContext* c,const cell_t* p) {
    if (p[1]<1 || p[1]>playerhelpers->GetMaxClients() || p[1]>speedwatch::kMaxSlots) return c->ThrowNativeError("Invalid client index %d",p[1]);
    if (p[4]!=speedwatch::kApiVersion || p[3]<static_cast<cell_t>(speedwatch::kSampleCells)) return c->ThrowNativeError("Unsupported API version or insufficient sample buffer");
    cell_t* out=nullptr; cell_t* end=nullptr;
    constexpr auto bytes=(speedwatch::kSampleCells-1)*sizeof(cell_t);
    // Windows SDK headers define max as a macro; keep this standard call opaque to it.
    if (p[2]<0 || p[2]>(std::numeric_limits<cell_t>::max)()-static_cast<cell_t>(bytes)
        || c->LocalToPhysAddr(p[2],&out)!=SP_ERROR_NONE
        || c->LocalToPhysAddr(p[2]+bytes,&end)!=SP_ERROR_NONE) return c->ThrowNativeError("Invalid output address");
    speedwatch::Identity identity;
    const auto* s=g_Core.Eligible(p[1],&identity) ? g_Core.observations.Sample(p[1],SpeedWatchNowUs()) : nullptr;
    if (s && (s->identity.serial!=identity.serial || s->identity.userId!=identity.userId)) s=nullptr;
    return speedwatch::EncodeSample(s,p[4],out,p[3]);
}
cell_t Status(IPluginContext*,const cell_t* p) {
    switch(p[1]) {
        case 0:return static_cast<cell_t>(g_Core.observations.Count());
        case 1:return static_cast<cell_t>(g_Core.observations.MemoryUsed());
        case 2:return static_cast<cell_t>(sizeof(speedwatch::ObservationService)+speedwatch::kMaxSlots*sizeof(speedwatch::Participant));
        default:return -1;
    }
}
}
const sp_nativeinfo_t g_CoreNatives[]={
    {"SpeedWatchCore_GetApiVersion",Version},{"SpeedWatchCore_GetCapabilities",Caps},
    {"SpeedWatchCore_Pulse",Pulse},{"SpeedWatchCore_SetParticipant",Participant},
    {"SpeedWatchCore_GetSample",Sample},{"SpeedWatchCore_GetStatus",Status},{nullptr,nullptr}
};
