#pragma once
#define SMEXT_CONF_NAME "L4D2 SpeedWatch Core"
#define SMEXT_CONF_DESCRIPTION "Observational usercmd block and invocation telemetry"
#define SMEXT_CONF_VERSION "0.9.0"
#define SMEXT_CONF_AUTHOR "Lechuga"
#define SMEXT_CONF_URL "https://github.com/AoC-Gamers/L4D2-SpeedWatch"
#define SMEXT_CONF_LOGTAG "SPEEDWATCH_CORE"
#define SMEXT_CONF_LICENSE "GPL-3.0-or-later"
#define SMEXT_CONF_DATESTRING __DATE__
#define SMEXT_LINK(name) SDKExtension *g_pExtensionIface = name;
#define SMEXT_CONF_METAMOD
#define SMEXT_ENABLE_PLAYERHELPERS
#define SMEXT_ENABLE_GAMEHELPERS
#define SMEXT_ENABLE_GAMECONF
#define SMEXT_ENABLE_PLUGINSYS
