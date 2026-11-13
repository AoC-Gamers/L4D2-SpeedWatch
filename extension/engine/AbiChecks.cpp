// Compile against the SDK with target x86 flags. These are SDK facts, not proof
// of a particular installed game binary. No runtime CUserCmd payload is accessed.
#include <eiface.h>
#include <shareddefs.h>
#include <usercmd.h>
#include <type_traits>
using ProcessUsercmdsPrototype = float (IServerGameClients::*)(edict_t*,bf_read*,int,int,int,bool,bool);
static_assert(std::is_same<decltype(&IServerGameClients::ProcessUsercmds),ProcessUsercmdsPrototype>::value,
    "L4D2 ProcessUsercmds ABI changed");
static_assert(sizeof(void*)==4 && sizeof(int)==4 && sizeof(float)==4,"x86 scalar ABI required");
static_assert(!std::is_standard_layout<CUserCmd>::value,"CUserCmd is polymorphic; do not use offsetof");
static_assert(alignof(CUserCmd)>=alignof(int),"Natural SDK alignment, no artificial packing");
