# ADCOS Application Model

## Core relationship

Applications are consumers of connectivity infrastructure.

```text
Application
    |
    | ConnectivityIntent
    v
ADCOS Exchange
    |
    | ConnectivityContract
    v
Provider execution
```

## Application-funded connectivity

An authorized application may purchase connectivity for itself, a device fleet,
a user cohort, a service gateway, or a provider-owned delegated endpoint.

The application receives a contract reference and operational status. It does
not receive authority over provider internals.

## Examples

### ShareNet

`ShareNet -> ADCOS -> gateway/relay connectivity -> content network`

### RoamLink

`RoamLink -> ADCOS -> wholesale provider connectivity -> mobile subscribers`

### COMOS

`COMOS -> ADCOS -> gateway/relay connectivity -> communication network`

## Product rule

ADCOS sells/allocates **connectivity outcomes**, not access technology.

Good:

```text
coverage=Ghana, availability>=99%, max_cost=..., beneficiaries=...
```

Bad:

```text
use provider X's gNB
use interface wlan0
create an IPsec tunnel to node Y
```

The latter belong to an execution adapter or network provider.
