import json

from commandlab.classifier import classify, Decision, CommandClassifier

import json

TEST_CASES: list[tuple[str, Decision]] = [
    # ── SAFE_EXECUTE ──────────────────────────────────────
    ("ls -la",                          Decision.SAFE_EXECUTE),
    ("grep -i error system.log",        Decision.SAFE_EXECUTE),
    ("cat readme.txt",                  Decision.SAFE_EXECUTE),
    ("echo hello world",                Decision.SAFE_EXECUTE),
    ("wc -l data.csv",                  Decision.SAFE_EXECUTE),
    ("awk '{print $3}' stats.txt",      Decision.SAFE_EXECUTE),
    ("head -n 5 access.log",            Decision.SAFE_EXECUTE),
    ("sed 's/foo/bar/g' config.txt",    Decision.SAFE_EXECUTE),   # no -i
    ("diff <(ls /etc) <(ls /usr/lib)",  Decision.SANDBOX),    # /etc in substitution → INSPECT
    # ── SANDBOX ───────────────────────────────────────────
    ("ps aux",                          Decision.SANDBOX),
    ("lsof -p $$",                      Decision.SANDBOX),
    ("ss -tulpn",                       Decision.SANDBOX),
    ("cat /proc/self/maps",             Decision.SANDBOX),
    ("cat /etc/passwd",                 Decision.SANDBOX),
    ("dig github.com",                  Decision.SANDBOX),
    ("strace ls",                       Decision.SANDBOX),
    ("ip addr",                         Decision.SANDBOX),
    ("ping -c 4 google.com",            Decision.SANDBOX),
    # ── TEXT_ONLY ─────────────────────────────────────────
    ("chmod 640 secret.key",            Decision.TEXT_ONLY),
    ("chown alice:finance report.pdf",  Decision.TEXT_ONLY),
    ("rm -rf /tmp/testdir",             Decision.TEXT_ONLY),
    ("mv new.conf app.conf",            Decision.TEXT_ONLY),
    ("touch notes.txt",                 Decision.TEXT_ONLY),
    ("ln -s v2.1 current",              Decision.TEXT_ONLY),
    ("sed -i 's/localhost/127.0.0.1/g' config.txt",  Decision.TEXT_ONLY),
    ("kill 4567",                       Decision.TEXT_ONLY),
    ("apt-get update",                  Decision.TEXT_ONLY),
    ("cp report.txt backup/",           Decision.TEXT_ONLY),
    # ── BLOCK ─────────────────────────────────────────────
    ("sudo apt update",                 Decision.BLOCK),
    ("iptables -A INPUT -p tcp --dport 8080 -j DROP", Decision.BLOCK),
    ("echo 1 > /proc/sys/net/ipv4/ip_forward",        Decision.BLOCK),
    ("mount /dev/sda1 /mnt",            Decision.BLOCK),
    ("tcpdump -i eth0 tcp port 443",    Decision.BLOCK),
    ("nc -zv 192.168.1.100 22",         Decision.BLOCK),
    ("shutdown -h now",                 Decision.BLOCK),
    ("dd if=/dev/zero of=/dev/sda",     Decision.BLOCK),
    ("chroot /mnt/newroot bash",        Decision.BLOCK),
    ("python3 server.py",               Decision.BLOCK),   # interpreter + args
    # ── chained commands ──────────────────────────────────
    ("ls && cat /etc/passwd",           Decision.SANDBOX),     # highest = INSPECT
    ("touch x && chmod 600 x",         Decision.TEXT_ONLY),   # highest = MODIFY
    ("ls | grep foo",                  Decision.SAFE_EXECUTE),
    ("ls && sudo rm -rf /",            Decision.BLOCK),        # sudo → CONTROL
    # ── obfuscation ───────────────────────────────────────
    ("$(ls)",                           Decision.SANDBOX),     # obfuscation → INSPECT
    ("`cat /etc/shadow`",               Decision.SANDBOX),
    ("eval 'rm -rf /'",                Decision.SANDBOX),     # obfuscation flag
]

clf = CommandClassifier()
passed = 0
failed = 0

print("=" * 72)
print(f"  CommandClassifier — test suite ({len(TEST_CASES)} cases)")
print("=" * 72)

for cmd, expected in TEST_CASES:
    result = clf.classify(cmd)
    ok = result.final_decision == expected
    symbol = "✓" if ok else "✗"
    if ok:
        passed += 1
    else:
        failed += 1
    status = f"got {result.final_decision.value}" if not ok else result.final_decision.value
    print(f"  {symbol} [{status:14s}]  {cmd!r}")
    if not ok:
        print(f"      expected: {expected.value}")
        for c in result.commands:
            print(f"      └─ base={c.base!r} risk={c.classification.value} reason={c.reason!r}")

print("=" * 72)
print(f"  Results: {passed} passed, {failed} failed out of {len(TEST_CASES)}")
print("=" * 72)

# Pretty-print one example
print()
print("── Example structured output ────────────────────────────────────────")
example = clf.classify("ls -la && cat /proc/self/maps | grep heap")
print(json.dumps(example.to_dict(), indent=2))
