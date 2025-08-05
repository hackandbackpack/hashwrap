# Hashwrap Compatibility Guide

## Hashcat Version Compatibility

### Supported Versions
- **Minimum Required**: hashcat v6.0.0
- **Tested With**: hashcat v6.2.6 (current stable)
- **Future Ready**: hashcat v7.0.0 (upcoming release)

### Version-Specific Features

#### hashcat v6.2.6 (Current Stable)
- ✅ All core features fully supported
- ✅ Hash detection for 40+ hash types
- ✅ Dictionary, mask, and hybrid attacks
- ✅ Rule-based attacks
- ✅ Performance optimization flags

#### hashcat v7.0.0 (Upcoming)
- ✅ New hash types pre-configured:
  - Argon2 variants (argon2i/d/id)
  - MetaMask and cryptocurrency wallets
  - Microsoft Online Account
  - SNMPv3, GPG, OpenSSH keys
  - LUKS2 encryption
  - JWT tokens
- ✅ Compatible with new backend systems (HIP, Metal)
- ✅ Ready for hash autodetection feature
- ✅ Supports new performance improvements

### Compatibility Matrix

| Feature | v6.0.0 | v6.2.6 | v7.0.0 |
|---------|--------|--------|--------|
| Basic attacks | ✅ | ✅ | ✅ |
| Hash detection | ✅ | ✅ | ✅+ |
| Hot-reload | ✅ | ✅ | ✅ |
| Security features | ✅ | ✅ | ✅ |
| New hash modes | ❌ | ❌ | ✅ |
| Auto-detection | ❌ | ❌ | Ready |

### Breaking Changes

None identified. Hashwrap maintains backward compatibility with all supported hashcat versions.

### Command Line Compatibility

All hashwrap commands remain consistent across hashcat versions:
```bash
# These work identically on all versions
python hashwrap.py config.json -m 0 -a 0
python hashwrap_v2.py auto crack hashes.txt
python hashwrap_v3.py auto crack hashes.txt --hot-reload
```

### Performance Considerations

- hashcat v7.0.0 includes significant performance improvements
- Memory management improvements remove 4GB limitations
- New backend support for Apple Silicon (M1/M2) via Metal
- HIP backend for modern AMD GPUs

### Migration Notes

No migration required. Hashwrap automatically detects the hashcat version and adjusts behavior accordingly.

### Testing

Hashwrap has been tested with:
- hashcat v6.2.6 on Linux, Windows, macOS
- hashcat v7.0.0-beta on Linux
- Various GPU configurations (NVIDIA, AMD, Intel)

### Future Enhancements

When hashcat v7.0.0 is released, hashwrap will be updated to leverage:
- Hash mode autodetection (omit -m flag)
- Python Bridge plugin integration
- Virtual backend devices
- Enhanced status reporting

### Troubleshooting

If you encounter compatibility issues:
1. Check hashcat version: `hashcat --version`
2. Ensure minimum version v6.0.0
3. Update hashcat if needed
4. Report issues to the hashwrap repository

### Contributing

To add support for new hash types:
1. Add pattern to `core/hash_analyzer.py`
2. Test with sample hashes
3. Submit pull request with test cases