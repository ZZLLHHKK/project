# Wakeword model placement

Put platform-specific Porcupine keyword files here:

- `linux_x86_64/wakeword.ppn`: desktop/Linux x86_64 model
- `raspberry_pi/wakeword.ppn`: Raspberry Pi ARM model

Runtime selection order:

1. `WAKEWORD_PPN_PATH` (if set)
2. `data/models/wakeword/<platform>/wakeword.ppn`
3. Legacy fallback paths (if present):
   - `models/wakeword.ppn`
   - `data/models/wakeword.ppn`

Current host target for this machine is `linux_x86_64`.
