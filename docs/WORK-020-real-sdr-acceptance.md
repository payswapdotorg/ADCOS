# WORK-020 real SDR acceptance run

## Result

```text
WORK-020 SDR-LAB RESULT: BLOCKED
WORK-020 CRITERION 4 = NOT ACCEPTED
```

The required physical SDR-based lab topology could not be run on this host.
No SDR hardware was fabricated or substituted with UERANSIM, a software-only
RAN, or the in-repo conformance server.

## Host and capability evidence

```text
Host: Tetevi-PC
OS: Ubuntu 25.04
Kernel: Linux 6.14.0-37-generic x86_64
CPU: Intel Core i5-10300H, 8 CPUs
RAM: 14 GiB
SUDO_NONINTERACTIVE: NO
SCTP: usable
TUN: /dev/net/tun present
```

`lsusb` reported only Linux Foundation USB hubs and an IMC Networks wireless
device. No USRP, LimeSDR, bladeRF, or other SDR device was present. No UHD,
SoapySDR, LimeSuite, or SDR device node was found. The host also lacks the
required OAI build tools (`cmake`, `meson`, `ninja`) and OAI binaries.

## Existing gate result

The WORK-020 branch was checked out from GitHub at commit `20e8ad4`. Running:

```text
RAN_INTEROP=1
RAN_PEER_KIND=real_oai
```

returned `UNREACHABLE`, with the capability matrix reporting:

```text
build_tools: missing cmake, meson, ninja
sdr_driver: no SDR device node
sctp: usable
tun: present
oai_binaries: none found
openran_control: 127.0.0.1:9091 refused
```

The deterministic `tools/ran_selftest.py` suite passes `32/32`. This does not
close the SDR criterion.

## Required follow-up environment

Run the unchanged gate on a host with an attached, authorized SDR; a supported
real OpenAirInterface/O-RAN build; a real radio UE; and a shielded or
authorized lab frequency. Capture `[SDR]`, `[CTRL]`, `[CELL]`, `[UE]`,
`[DRB]`, and `[IP]` evidence with payload SHA-256 before claiming acceptance.
